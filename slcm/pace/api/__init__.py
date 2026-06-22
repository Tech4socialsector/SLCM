import frappe
import math

@frappe.whitelist(allow_guest=True)
def get_pace_programmes():
    programmes = frappe.get_all('PACE Programme', fields=[
        'name', 'programme_name', 'programme_code', 'programme_prefix',
        'admission_status', 'show_overview_tab', 'overview as description',
        'duration', 'duration_type', 'banner_image as image_url', 'route'
    ], filters={'published': 1}, order_by='creation desc')
    
    for p in programmes:
        p['duration_label'] = f"{p.duration} {p.duration_type}" if p.duration and p.duration_type else ""
        
    return programmes

@frappe.whitelist(allow_guest=True)
def get_pace_faqs(faq_page=1):
    faq_page = int(faq_page)
    page_size = 10
    start = (faq_page - 1) * page_size
    
    faqs = frappe.get_all('PACE FAQs', fields=['question', 'answer'], order_by='creation desc', limit_start=start, limit_page_length=page_size)
    total_count = frappe.db.count('PACE FAQs')
    
    return {
        'success': True,
        'faqs': faqs,
        'faq_page': faq_page,
        'faq_total_pages': math.ceil(total_count / page_size) if total_count > 0 else 1
    }

@frappe.whitelist(allow_guest=True)
def get_pace_page_data():
    config = frappe.get_single('Applicant Portal Config')
    
    active_admission_data = frappe.db.get_value("PACE Admission", {"status": "Active", "docstatus": ["<", 2]}, ["name", "academic_year"], as_dict=True)
    academic_year = active_admission_data.academic_year if active_admission_data else ""
    if not academic_year:
        academic_year = frappe.db.get_value("Academic Year", {"status": "Active"}, "name") or ""
        
    hero_badge_text = f"Admission Open for {academic_year}" if academic_year else ""
    
    data = {
        'success': True,
        'show_ticker': config.show_ticker,
        'hero_background_image': config.hero_background_image,
        'hero_title': config.hero_title,
        'hero_subtitle': config.hero_subtitle,
        'hero_description': config.hero_description,
        'hero_cta_label': config.hero_cta_label,
        'hero_cta2_label': config.hero_cta2_label,
        'hero_badge_text': hero_badge_text,
        'ticker_items': [],
        'programmes': get_pace_programmes()
    }
    
    if config.show_ticker:
        data['ticker_items'] = frappe.get_all('PACE News Ticker', fields=['ticker_text', 'ticker_link', 'first_priority'], filters={'parent': 'Applicant Portal Config', 'parenttype': 'Applicant Portal Config'}, order_by='idx asc')
        
    faq_data = get_pace_faqs(1)
    data['faqs'] = faq_data.get('faqs', [])
    data['faq_total_pages'] = faq_data.get('faq_total_pages', 1)
    data['faq_page'] = 1
    
    return data

@frappe.whitelist(allow_guest=True)
def submit_pace_enquiry(full_name, email, phone, programme_of_interest):
    try:
        enquiry = frappe.get_doc({
            'doctype': 'PACE Enquiry',
            'full_name': full_name,
            'email': email,
            'phone': phone,
            'programme_of_interest': programme_of_interest,
            'status': 'New'
        })
        enquiry.insert(ignore_permissions=True)
        return {"success": True, "message": "Enquiry submitted successfully"}
    except Exception as e:
        frappe.log_error("PACE Enquiry Submission Failed", str(e))
        return {"success": False, "message": "Failed to submit enquiry. Please try again later."}

@frappe.whitelist()
def get_user_pace_applications():
    if frappe.session.user == 'Guest':
        return []
    
    apps = frappe.get_all('PACE Application', fields=['name', 'programme', 'status'], filters={'owner': frappe.session.user}, order_by='creation desc')
    
    return apps

@frappe.whitelist()
def get_verifiers(doctype=None, txt=None, searchfield=None, start=0, page_len=20, filters=None, *args, **kwargs):
    # Search text filter
    search_cond = ""
    params = {}
    if txt:
        search_cond = "AND (u.name LIKE %(txt)s OR u.full_name LIKE %(txt)s)"
        params["txt"] = f"%{txt}%"
        
    query = f"""
        SELECT DISTINCT u.name, u.full_name
        FROM `tabUser` u
        LEFT JOIN `tabHas Role` r ON r.parent = u.name
        LEFT JOIN `tabPACE Verifier Mapping` m ON m.user = u.name
        WHERE u.enabled = 1 
          AND u.name NOT IN ('Guest', 'Administrator')
          AND (
            r.role IN ('Document Verifier', 'PACE Admission Manager', 'Document Verification Admin', 'Admission Admin', 'Admission Manager', 'Admission Officer', 'PACE Verification Admin')
            OR m.user IS NOT NULL
          )
          {search_cond}
        LIMIT %(start)s, %(page_len)s
    """
    params["start"] = int(start or 0)
    params["page_len"] = int(page_len or 20)
    
    res = frappe.db.sql(query, params, as_list=True)
    return res

@frappe.whitelist()
def bulk_assign_verifications(verifier, verification_names):
    import json
    from slcm.pace.assignment_logic import get_sla_days, send_verifier_assignment_email
    from frappe.utils import add_days, nowdate
    
    if isinstance(verification_names, str):
        verification_names = json.loads(verification_names)
        
    # Permission Check
    roles = frappe.get_roles()
    if "PACE Admission Manager" not in roles and "System Manager" not in roles and "Admission Admin" not in roles and "Document Verification Admin" not in roles and "PACE Verification Admin" not in roles:
        frappe.throw(frappe._("You are not authorized to perform bulk assignment."))
        
    count = 0
    assigned_docs = []
    for name in verification_names:
        doc = frappe.get_doc("PACE Document Verification", name)
        # Only assign if pending
        if doc.status == "Pending":
            doc.assigned_verifier = verifier
            app_name = doc.get("application") or doc.get("pace_application")
            days = get_sla_days(app_name)
            doc.due_date = add_days(nowdate(), days)
            doc.is_overdue = 0
            doc.flags.ignore_assignment_email = True
            doc.flags.ignore_permissions = True
            doc.save(ignore_permissions=True)
            
            # Sync back to PACE Application
            if app_name:
                frappe.db.set_value("PACE Application", app_name, "assigned_verifier", verifier, update_modified=True)
            
            assigned_docs.append(doc)
            count += 1
            
    if assigned_docs:
        send_verifier_assignment_email(verifier, assigned_docs)
        
    return {
        "status": "success",
        "assigned_count": count
    }

# ─────────────────────────────────────────────────────────────────────────────
#  RAZORPAY PAYMENT (Desk/Portal)
# ─────────────────────────────────────────────────────────────────────────────

from slcm.pace.api.service.pace_payment import (
    _update_pace_payment_request,
    _get_active_pace_admission_name
)

@frappe.whitelist()
def create_pace_razorpay_order(assignment_name):
    from slcm.pace.api.service.pace_payment import create_pace_razorpay_order as _create
    return _create(assignment_name)

@frappe.whitelist()
def verify_pace_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, assignment_name):
    from slcm.pace.api.service.pace_payment import verify_pace_payment as _verify
    return _verify(razorpay_payment_id, razorpay_order_id, razorpay_signature, assignment_name)

@frappe.whitelist()
def portal_reupload_document(application, fieldname, filedata, filename):
    import json
    
    # 1. Validation
    if not application or not fieldname or not filedata:
        return {"status": "error", "message": "Missing required parameters"}
        
    if not frappe.db.exists("PACE Application", application):
        return {"status": "error", "message": "Application not found"}
        
    doc = frappe.get_doc("PACE Application", application)
    
    # Check permissions
    if frappe.session.user == "Guest":
        return {"status": "error", "message": "You must be logged in to upload documents"}
        
    user_email = frappe.db.get_value("User", frappe.session.user, "email") or frappe.session.user
    if doc.owner != frappe.session.user and doc.email_address != user_email and "System Manager" not in frappe.get_roles():
        return {"status": "error", "message": "Not authorized to upload to this application"}
        
    # 2. Save File
    try:
        from frappe.utils.file_manager import save_file
        
        # Clean up base64 payload if it includes data URI scheme
        if "," in filedata:
            filedata = filedata.split(",")[1]
            
        saved_file = save_file(
            fname=filename,
            content=filedata,
            dt="PACE Application",
            dn=application,
            folder="Home/Attachments",
            decode=True,
            is_private=1,
            df=fieldname
        )
        
        # Route it through the central attachment handler to ensure renaming and privacy rules
        doc.set(fieldname, saved_file.file_url)
        if hasattr(doc, "handle_attachments"):
            doc.handle_attachments()
            
        final_file_url = doc.get(fieldname)
        
        # Update PACE Application
        doc.db_set(fieldname, final_file_url)
        
        # 3. Update PACE Document Verification if exists
        verification_name = frappe.db.get_value("PACE Document Verification", {"application": application})
        if verification_name:
            v_doc = frappe.get_doc("PACE Document Verification", verification_name)
            from frappe.utils import now_datetime
            
            updated = False
            for item in v_doc.verification_items:
                if item.fieldname == fieldname:
                    item.file = final_file_url
                    item.is_reuploaded = 1
                    item.reuploaded_on = now_datetime()
                    updated = True
                    
            if updated:
                v_doc.has_reuploaded_items = 1
                v_doc.flags.ignore_permissions = True
                v_doc.save(ignore_permissions=True)
                
        return {"status": "success", "message": "Document uploaded successfully", "file_url": final_file_url}
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Portal Reupload Document Error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist(methods=["POST", "GET"])
def download_pace_document(application_name, fieldname):
    """Stream a private document (application_form, admission_letter) for the logged-in user."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(frappe._("Please log in to download documents."), frappe.AuthenticationError)
        
    if fieldname not in ["application_form", "admission_letter"]:
        frappe.throw(frappe._("Document type not allowed."), frappe.PermissionError)
        
    try:
        doc = frappe.get_doc("PACE Application", application_name, ignore_permissions=True)
    except frappe.DoesNotExistError:
        frappe.throw(frappe._("Application not found"))

    user_email = frappe.db.get_value("User", user, "email") or user
    if doc.owner != user and doc.email_address != user_email:
        roles = frappe.get_roles()
        if "Admission Admin" not in roles and "System Manager" not in roles and "PACE Admission Manager" not in roles and "PACE Verification Admin" not in roles:
            frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    file_url = getattr(doc, fieldname, None)
    if not file_url:
        frappe.throw(frappe._("Document not generated yet."))
        
    file_doc = frappe.db.get_value("File", {"file_url": file_url}, ["name", "file_name"], as_dict=True)
    if not file_doc:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = file_url
        return
        
    from frappe.utils.file_manager import get_file
    fname, content = get_file(file_doc.name)
    frappe.local.response.filename = fname
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"
