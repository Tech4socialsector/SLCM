import frappe
import json
from urllib.parse import quote
from frappe import _, throw
from frappe.utils import flt, now_datetime, get_url, strip_html_tags

@frappe.whitelist()
def create_pace_razorpay_order(assignment_name):
    """
    Creates a Razorpay order for a PACE fee assignment.
    """
    try:
        assignment = frappe.get_doc("PACE Applicant Fee Assignment", assignment_name)
        
        if assignment.status == "Paid":
            frappe.throw(_("This fee assignment has already been paid."))
        
        if flt(assignment.final_payable_amount) <= 0:
            frappe.throw(_("The payable amount must be greater than zero."))

        # Find the matching active fee structure to get the payment gateway
        filters = {
            "pace_program": assignment.program,
            "status": "Active"
        }
        if assignment.academic_year:
            filters["academic_year"] = assignment.academic_year

        matching = frappe.get_all(
            "PACE Fee Structure",
            filters=filters,
            order_by="valid_from desc",
            limit=1
        )
        if not matching:
            frappe.throw(_("No active Fee Structure found for program {0} and year {1}.").format(assignment.program, assignment.academic_year))
        
        fee_structure = frappe.get_doc("PACE Fee Structure", matching[0].name)
        gateway = fee_structure.payment_gateway
        if not gateway:
            gateway = frappe.db.get_value("Payment Gateway", {"is_default": 1}, "name") or "Razorpay"

        from payments.utils import get_payment_gateway_controller
        controller = get_payment_gateway_controller(gateway)
        if not controller:
            frappe.throw(_("Payment Gateway '{0}' not found or not configured.").format(gateway))

        app = frappe.get_doc("PACE Application", assignment.applicant)
        payer_email = app.email_address or frappe.session.user
        if payer_email == "Administrator":
            payer_email = "admin@example.com" # Razorpay requires a valid email format

        # Check if a valid Payment Request with a Razorpay Order ID already exists
        existing_pr = frappe.db.get_value("Payment Request", {
            "reference_doctype": "PACE Applicant Fee Assignment",
            "reference_name": assignment.name,
            "status": "Requested",
            "razorpay_order_id": ["!=", ""]
        }, ["name", "razorpay_order_id"], as_dict=True)

        if existing_pr:
            order_id = existing_pr.razorpay_order_id
            # We'll just return this order ID instead of creating a new one
            # Note: In a production app, you might want to verify with Razorpay if this order is still valid/not expired.
            return {
                "order_id": order_id,
                "key_id": controller.api_key,
                "amount": flt(assignment.final_payable_amount) * 100, # Razorpay expects paise
                "currency": fee_structure.currency or "INR",
                "gateway": gateway,
                "payer_email": payer_email
            }

        payment_details = {
            "amount": flt(assignment.final_payable_amount),
            "title": _("PACE Fee Payment"),
            "description": _("Fee Payment for {0}").format(assignment.program),
            "reference_doctype": "PACE Applicant Fee Assignment",
            "reference_docname": assignment.name,
            "payer_email": payer_email,
            "payer_name": assignment.applicant_name,
            "currency": fee_structure.currency or "INR",
            "receipt": (assignment.name[:40])
        }

        order = controller.create_order(**payment_details)
        
        if not order or not order.get("id"):
            frappe.throw(_("Order creation failed. Please check gateway logs."))

        # Update/Create Payment Request
        _update_pace_payment_request(assignment, gateway, order.get("id"), "Requested", response_data=order)

        return {
            "order_id": order.get("id"),
            "key_id": controller.api_key,
            "amount": order.get("amount"),
            "currency": order.get("currency"),
            "gateway": gateway,
            "payer_email": payer_email
        }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "PACE Payment Order Creation Failed")
        raise

@frappe.whitelist()
def verify_pace_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, assignment_name):
    """
    Verifies the Razorpay payment for a PACE fee assignment.
    """
    try:
        assignment = frappe.get_doc("PACE Applicant Fee Assignment", assignment_name)
        
        # Get gateway from Payment Request
        pr_name = frappe.db.get_value("Payment Request", {
            "reference_doctype": "PACE Applicant Fee Assignment",
            "reference_name": assignment.name,
            "razorpay_order_id": razorpay_order_id
        }, "name")
        
        if not pr_name:
            frappe.throw(_("Payment Request not found for order {0}").format(razorpay_order_id))
        
        pr = frappe.get_doc("Payment Request", pr_name)
        gateway = pr.payment_gateway

        from payments.utils import get_payment_gateway_controller
        controller = get_payment_gateway_controller(gateway)
        
        # Verify Signature
        body = razorpay_order_id + "|" + razorpay_payment_id
        api_secret = controller.get_password("api_secret")
        
        controller.verify_signature(body, razorpay_signature, api_secret)
        
        # Success Logic
        assignment.status = "Paid"
        assignment.transaction_id = razorpay_payment_id
        assignment.payment_date = now_datetime().date()
        assignment.save(ignore_permissions=True)
        
        # Update Payment Request
        _update_pace_payment_request(assignment, gateway, razorpay_order_id, "Paid", razorpay_payment_id, 
            response_data={"payment_id": razorpay_payment_id, "signature": razorpay_signature})
        
        # The receipt creation and application status update are now handled 
        # inside assignment.on_update() -> on_payment_paid()
        # and we update application status here for immediate effect or keep it here
        frappe.db.set_value("PACE Application", assignment.applicant, "status", "Fee Paid")

        return {"status": "success"}

    except Exception:
        frappe.log_error(frappe.get_traceback(), "PACE Payment Verification Failed")
        return {"status": "failed", "message": _("Payment verification failed.")}

def _create_pace_receipt(assignment, transaction_id=None):
    """
    Internal utility to create a PACE Receipt after payment.
    """
    # Avoid duplicates
    if frappe.db.exists("PACE Receipt", {"fee_assignment": assignment.name}):
        return frappe.get_doc("PACE Receipt", {"fee_assignment": assignment.name})

    # Find corresponding Payment Request
    pr_name = frappe.db.get_value("Payment Request", {
        "reference_doctype": "PACE Applicant Fee Assignment",
        "reference_name": assignment.name,
        "status": ["!=", "Cancelled"]
    }, "name", order_by="creation desc")
    
    pr_doc = None
    if pr_name:
        pr_doc = frappe.get_doc("Payment Request", pr_name)

    receipt = frappe.new_doc("PACE Receipt")
    receipt.pace_application = assignment.applicant
    receipt.fee_assignment = assignment.name
    receipt.payment_request = pr_name
    receipt.applicant_name = assignment.applicant_name
    receipt.program = assignment.program
    receipt.fee_type = assignment.fee_type
    receipt.amount = assignment.final_payable_amount
    receipt.currency = assignment.currency
    receipt.academic_year = assignment.academic_year
    
    # Use provided transaction_id, or from assignment, or from Payment Request
    final_transaction_id = (
        transaction_id or 
        assignment.get("transaction_id") or 
        (pr_doc.razorpay_payment_id if pr_doc else None) or 
        (pr_doc.transaction_id if pr_doc else None) or
        "Manual"
    )
    receipt.transaction_id = final_transaction_id
    
    # Use assignment payment date, or now
    receipt.payment_date = assignment.get("payment_date") or now_datetime()
    
    receipt.insert(ignore_permissions=True)
    return receipt

def _update_pace_payment_request(assignment, gateway, transaction_id, status, payment_id=None, response_data=None):
    """
    Internal utility to update/create Payment Request for PACE assignments.
    """
    pr_name = frappe.db.get_value("Payment Request", {
        "reference_doctype": "PACE Applicant Fee Assignment",
        "reference_name": assignment.name,
        "status": ["!=", "Cancelled"]
    }, "name", order_by="creation desc")

    if pr_name:
        pr = frappe.get_doc("Payment Request", pr_name)
    else:
        pr = frappe.new_doc("Payment Request")
        pr.reference_doctype = "PACE Applicant Fee Assignment"
        pr.reference_name = assignment.name
        pr.amount = assignment.final_payable_amount
        pr.currency = assignment.currency or "INR"
        app_email = frappe.db.get_value("PACE Application", assignment.applicant, "email_address")
        pr.email_to = app_email or frappe.session.user

    # If document is already submitted, we must use db_set to avoid "Cannot Update After Submit" error
    if pr.name and pr.docstatus == 1:
        update_values = {
            "payment_gateway": gateway
        }
        if status == "Requested":
            update_values["razorpay_order_id"] = transaction_id
            update_values["status"] = "Requested"
        elif status == "Paid":
            update_values["status"] = "Paid"
            update_values["razorpay_payment_id"] = payment_id
            update_values["transaction_id"] = payment_id

        if response_data:
            update_values["gateway_response"] = json.dumps(response_data, indent=4)
        
        frappe.db.set_value("Payment Request", pr.name, update_values)
    else:
        # Document is either new or in Draft status
        pr.payment_gateway = gateway
        
        if status == "Requested":
            pr.razorpay_order_id = transaction_id
            pr.status = "Requested"
        elif status == "Paid":
            pr.status = "Paid"
            pr.razorpay_payment_id = payment_id
            pr.transaction_id = payment_id

        if response_data:
            pr.gateway_response = json.dumps(response_data, indent=4)

        if pr.name:
            pr.save(ignore_permissions=True)
        else:
            pr.insert(ignore_permissions=True)

        if status in ["Paid", "Requested"] and pr.docstatus == 0:
            pr.submit()
    
    frappe.db.commit()


def _abs_url(path: str | None) -> str:
    path = (path or "").strip()
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return get_url(path)


def _safe_error(message: str, exc: Exception | None = None) -> dict:
    if exc:
        frappe.log_error(frappe.get_traceback(), "PACE API")
    if exc and getattr(frappe.conf, "developer_mode", 0):
        return {"success": False, "message": f"{message} ({exc})"}
    return {"success": False, "message": message}


def _get_active_pace_admission_name(academic_year=None) -> str | None:
    filters = {"status": "Active"}
    if academic_year:
        filters["academic_year"] = academic_year
    return frappe.db.get_value("PACE Admission", filters, "name", order_by="creation desc")


@frappe.whitelist(allow_guest=True)
def get_pace_programmes(academic_year=None):
    """
    Programmes from the active PACE Admission (child table PACE Admission Programme),
    enriched from PACE Programme. Only includes published programmes.

    Each item includes detail_slug for URLs: /pace/admission/<detail_slug>
    """
    pace_admission = _get_active_pace_admission_name(academic_year=academic_year)
    if not pace_admission:
        return []

    rows = frappe.get_all(
        "PACE Admission Programme",
        filters={"parent": pace_admission, "parenttype": "PACE Admission"},
        fields=[
            "programme",
            "status",
            "total_seats",
            "max_applications",
            "application_received",
            "application_fee_indian",
            "application_fee_foreign",
        ],
        order_by="idx asc",
    )

    out = []
    for row in rows:
        if not row.programme:
            continue

        p = frappe.db.get_value(
            "PACE Programme",
            row.programme,
            [
                "name",
                "programme_name",
                "programme_prefix",
                "programme_code",
                "route",
                "published",
                "overview",
                "show_overview_tab",
                "duration",
                "duration_type",
                "admission_status",
                "banner_image",
            ],
            as_dict=True,
        )
        if not p or not p.published:
            continue

        slug = (p.route or "").strip() or p.name
        overview_plain = strip_html_tags(p.overview or "").strip()
        if len(overview_plain) > 240:
            overview_plain = overview_plain[:237] + "…"

        dur = p.duration
        dt = p.duration_type or "Year"
        duration_label = ""
        if dur is not None and dur != "":
            try:
                n = int(dur)
                unit = "Year" if dt == "Year" else "Month"
                duration_label = f"{n} {unit}{'s' if n != 1 else ''}"
            except (TypeError, ValueError):
                duration_label = str(dur)

        image = _abs_url(p.banner_image)

        admission_status = (p.admission_status or "Closed").strip() or "Closed"

        out.append(
            {
                "programme": p.name,
                "name": p.name,
                "programme_name": p.programme_name or p.name,
                "programme_prefix": p.programme_prefix or "PACE PROGRAMME",
                "programme_code": p.programme_code or "",
                "show_overview_tab": p.show_overview_tab,
                "programme_type": "PACE PROGRAMME",
                "route": p.route,
                "detail_slug": slug,
                "detail_url": f"/pace/admission/{quote(slug, safe='')}",
                "description": overview_plain,
                "short_description": overview_plain,
                "duration_label": duration_label,
                "duration": p.duration,
                "admission_status": row.status or p.admission_status or "Closed",
                "image_url": image,
                "programme_image": image,
                "total_seats": row.total_seats,
                "max_applications": row.max_applications,
                "application_received": row.application_received,
                "application_fee_indian": row.application_fee_indian,
                "application_fee_foreign": row.application_fee_foreign,
            }
        )

    return out


@frappe.whitelist(allow_guest=True)
def get_pace_page_data():
    """
    Composite payload for /pace/admission page.
    """
    try:
        pc = frappe.get_single("Applicant Portal Config")

        ticker_items = []
        for row in pc.get("ticker_items") or []:
            if (row.is_active or 0) == 1:
                ticker_items.append(
                    {"ticker_text": row.ticker_text or "", "ticker_link": row.ticker_link or ""}
                )

        faqs = frappe.get_all(
            "PACE FAQs",
            filters={"category": "Admission", "is_programme_specific": 0},
            fields=["question", "answer"],
            order_by="creation desc",
        )

        programmes = []
        pace_admission = _get_active_pace_admission_name()
        hero_badge = (pc.get("hero_badge_text") or "").strip()

        if pace_admission:
            # Dynamically fetch academic year from the active admission record
            academic_year = frappe.db.get_value("PACE Admission", pace_admission, "academic_year")
            if academic_year:
                hero_badge = f"Enrolling Now for {academic_year}"

            rows = frappe.get_all(
                "PACE Admission Programme",
                filters={"parent": pace_admission, "parenttype": "PACE Admission"},
                fields=["programme", "status"],
                order_by="idx asc",
            )
            for r in rows:
                if not r.programme:
                    continue
                p = frappe.db.get_value(
                    "PACE Programme",
                    r.programme,
                    [
                        "name",
                        "programme_name",
                        "programme_prefix",
                        "programme_code",
                        "route",
                        "published",
                        "overview",
                        "show_overview_tab",
                        "duration",
                        "duration_type",
                        "banner_image",
                    ],
                    as_dict=True,
                )
                if not p or not p.published:
                    continue

                slug = (p.route or "").strip() or p.name
                duration_label = "—"
                if p.duration and p.duration_type:
                    n = p.duration
                    unit = p.duration_type
                    duration_label = f"{n} {unit}{'s' if n != 1 else ''}"

                programmes.append(
                    {
                        "name": p.name,
                        "programme": p.name,
                        "programme_name": p.programme_name or p.name,
                        "programme_prefix": p.programme_prefix or "PACE PROGRAMME",
                        "programme_code": p.programme_code or "",
                        "show_overview_tab": p.show_overview_tab,
                        "programme_type": "PACE PROGRAMME",
                        "image_url": _abs_url(p.banner_image),
                        "programme_image": _abs_url(p.banner_image),
                        "description": strip_html_tags(p.overview or "").strip(),
                        "short_description": strip_html_tags(p.overview or "").strip(),
                        "duration_label": duration_label,
                        "duration": p.duration,
                        "duration_type": p.duration_type or "",
                        "admission_status": r.status or "Closed",
                        "detail_url": f"/pace/admission/{quote(slug, safe='')}",
                    }
                )

        return {
            "success": True,
            "hero_title": (pc.get("hero_title") or "").strip(),
            "hero_subtitle": (pc.get("hero_subtitle") or "").strip(),
            "hero_description": (pc.get("hero_description") or "").strip(),
            "hero_badge_text": hero_badge,
            "hero_background_image": _abs_url(pc.get("hero_background_image")),
            "hero_cta_label": (pc.get("hero_cta_label") or "").strip(),
            "hero_cta2_label": (pc.get("hero_cta2_label") or "").strip(),
            "hero_prospectus_file": _abs_url(pc.get("hero_prospectus_file")),
            "show_ticker": int(pc.get("show_ticker") or 0),
            "enable_pace_admission": int(pc.get("enable_pace_admission") or 0),
            "ticker_items": ticker_items,
            "faqs": faqs or [],
            "programmes": programmes,
            "contact_email": (pc.get("contact_email") or "").strip(),
            "support_email": (pc.get("support_email") or "").strip(),
        }
    except Exception as e:
        return _safe_error("Could not load PACE page data.", e)


@frappe.whitelist(allow_guest=True)
def submit_pace_enquiry(full_name=None, email=None, phone=None, programme_of_interest=None):
    try:
        full_name = (full_name or "").strip()
        email = (email or "").strip()
        phone = (phone or "").strip()
        programme_of_interest = (programme_of_interest or "").strip()

        if not full_name or not email or not phone or not programme_of_interest:
            return _safe_error("All fields are required.")

        pc = frappe.get_single("Applicant Portal Config")
        notify_to = (pc.get("contact_email") or "").strip()
        if not notify_to:
            return _safe_error("Contact email is not configured.")

        doc = frappe.get_doc(
            {
                "doctype": "PACE Enquiry",
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "programme_of_interest": programme_of_interest,
                "status": "New",
            }
        )
        doc.insert(ignore_permissions=True)

        subject = f"New PACE Programme Enquiry — {programme_of_interest}"
        message = (
            "<p>A new PACE programme enquiry has been submitted.</p>"
            "<ul>"
            f"<li><b>Full Name</b>: {frappe.utils.escape_html(full_name)}</li>"
            f"<li><b>Email</b>: {frappe.utils.escape_html(email)}</li>"
            f"<li><b>Phone</b>: {frappe.utils.escape_html(phone)}</li>"
            f"<li><b>Programme of Interest</b>: {frappe.utils.escape_html(programme_of_interest)}</li>"
            "</ul>"
        )
        frappe.sendmail(recipients=[notify_to], subject=subject, message=message, delayed=False)

        return {"success": True}
    except Exception as e:
        return _safe_error("Could not submit enquiry. Please try again.", e)

@frappe.whitelist()
def reset_verification_status(application, fieldname, file=None):
    """
    Resets the verification status of a document item when it is re-uploaded.
    """
    verification_name = frappe.db.get_value("PACE Document Verification", {"application": application}, "name")
    if not verification_name:
        return {"status": "error", "message": "Verification record not found."}

    verification = frappe.get_doc("PACE Document Verification", verification_name)
    updated = False

    found = False
    for row in verification.verification_items:
        if row.fieldname == fieldname:
            found = True
            # Always update the file if provided, regardless of status
            if file:
                row.file = file
                updated = True
            
            # Only reset to Pending and mark as re-uploaded if it was officially Returned
            if row.status == "Returned for Correction":
                row.status = "Pending"
                row.remarks = ""
                row.is_reuploaded = 1
                row.reuploaded_on = frappe.utils.now_datetime()
                updated = True

    if not found:
        # Add missing document to verification items
        meta = frappe.get_meta("PACE Application")
        field_label = meta.get_label(fieldname)
        verification.append("verification_items", {
            "document_name": field_label or fieldname,
            "fieldname": fieldname,
            "file": file,
            "status": "Pending",
            "is_reuploaded": 1,
            "reuploaded_on": frappe.utils.now_datetime()
        })
        updated = True

    if updated:
        # If any item was actually reset to Pending, mark the parent for admin review
        if any(r.status == "Pending" and r.is_reuploaded for r in verification.verification_items):
            verification.has_reuploaded_items = 1
            
        verification.save(ignore_permissions=True)
        return {"status": "success"}
    
    return {"status": "not_found"}

@frappe.whitelist()
def portal_reupload_document(application, fieldname, filedata, filename):
    """
    Sudo-level upload for portal users when they need to re-upload.
    Checks both owner and email_address to avoid 403 Forbidden for authorized users.
    """
    from frappe import _
    import base64

    # 1. Verify ownership or applicant email
    app_data = frappe.db.get_value("PACE Application", application, ["owner", "email_address"], as_dict=True)
    if not app_data:
        frappe.throw(_("Application {0} not found.").format(application), frappe.NotFoundError)

    # Check if user is authorized: Administrator, Owner, or Email Address matches session user
    is_authorized = (
        frappe.session.user == "Administrator" or
        app_data.owner == frappe.session.user or
        (app_data.email_address and app_data.email_address == frappe.session.user)
    )

    if not is_authorized:
        # Log details for debugging 403 errors
        frappe.log_error(
            f"Unauthorized re-upload attempt on {application}. User: {frappe.session.user}, Owner: {app_data.owner}, Email: {app_data.email_address}",
            "PACE Portal Permission Error"
        )
        frappe.throw(_("Not authorized to update this application."), frappe.PermissionError)
    
    # 2. Decode and save the file
    try:
        if "," in filedata:
            filedata = filedata.split(",")[1]
        
        file_content = base64.b64decode(filedata)
        
        # Save file and attach to document
        _file = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "attached_to_doctype": "PACE Application",
            "attached_to_name": application,
            "attached_to_field": fieldname,
            "content": file_content,
            "is_private": 1
        })
        _file.insert(ignore_permissions=True)
        
        # 3. Reset verification status using the established logic
        return reset_verification_status(application, fieldname, _file.file_url)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Portal Re-upload Failed")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_unassigned_applications(filters=None, limit=100):
    """
    Fetch PACE Applications that are Submitted but NOT yet assigned to a verifier.
    """
    import json
    if filters and isinstance(filters, str):
        filters = json.loads(filters)
    
    # Base filters: Must be Submitted and have no assigned_verifier
    base_filters = filters or {}
    base_filters.update({
        "status": "Submitted",
        "assigned_verifier": ["in", ["", None]]
    })
    
    records = frappe.get_all("PACE Application", 
        filters=base_filters, 
        fields=["name", "applicant_name", "programme", "academic_year"],
        order_by="creation desc",
        limit=int(limit)
    )
    
    return records

@frappe.whitelist()
def bulk_assign_applications(verifier, count=0, filters=None, app_names=None):
    """
    Bulk assign PACE Applications to a verifier and trigger verification record creation.
    """
    from frappe import _
    import json
    from slcm.pace.doctype.pace_document_verification.get_document_api import generate_document_verification
    
    if not verifier:
        frappe.throw(_("Please select a verifier."))
    
    targets = []
    if app_names:
        if isinstance(app_names, str):
            app_names = json.loads(app_names)
        targets = app_names
    elif count:
        count = int(count)
        if count <= 0:
            frappe.throw(_("Please specify a valid count."))
            
        if filters and isinstance(filters, str):
            filters = json.loads(filters)
        
        # Fetch matching unassigned apps
        filters = filters or {}
        filters.update({
            "status": "Submitted",
            "assigned_verifier": ["in", ["", None]]
        })
        
        records = frappe.get_all("PACE Application", filters=filters, fields=["name"], limit=count)
        targets = [r.name for r in records]
    else:
        frappe.throw(_("Please select applications or specify a count."))

    assigned_count = 0
    assigned_details = []
    
    for app_name in targets:
        # Update Application
        frappe.db.set_value("PACE Application", app_name, "assigned_verifier", verifier)
        
        # Create/Update Verification Record
        generate_document_verification(app_name)
        
        # Collect info for notification
        app_info = frappe.db.get_value("PACE Application", app_name, ["name", "applicant_name", "programme"], as_dict=True)
        if app_info:
            assigned_details.append(app_info)
        
        assigned_count += 1
    
    if assigned_count > 0:
        send_verifier_assignment_notifications(verifier, assigned_details)
            
    return {"status": "success", "assigned_count": assigned_count}

def send_verifier_assignment_notifications(verifier, targets):
    """
    Sends email and system notification to the assigned verifier.
    """
    try:
        # 1. Get Verifier Info
        verifier_doc = frappe.get_doc("User", verifier)
        verifier_email = verifier_doc.email
        verifier_name = verifier_doc.full_name or verifier
        
        # 2. System Notification
        message_body = f"<p>You have been assigned <strong>{len(targets)}</strong> new PACE applications for document verification.</p>"
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"New Assignments: {len(targets)} PACE Applications",
            "for_user": verifier,
            "type": "Alert",
            "email_content": message_body,
            "from_user": frappe.session.user or "Administrator",
            "link": "/desk/pace-document-verification"
        }).insert(ignore_permissions=True)

        # 3. Email Template
        template_name = "PACE Verifier Assignment"
        if frappe.db.exists("Email Template", template_name):
            email_template = frappe.get_doc("Email Template", template_name)
            args = {
                "verifier_name": verifier_name,
                "targets": targets,
                "count": len(targets)
            }
            
            subject = frappe.render_template(email_template.subject or "New Applications Assigned", args)
            
            # Use appropriate message field from template
            content = ""
            if email_template.get("use_html") and email_template.get("response_html"):
                content = frappe.render_template(email_template.response_html, args)
            elif email_template.get("response"):
                content = frappe.render_template(email_template.response, args)
            else:
                content = frappe.render_template(email_template.get("message") or "", args)

            if content:
                frappe.sendmail(
                    recipients=[verifier_email],
                    subject=subject,
                    content=content,
                    now=False
                )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Verifier Notification Failed")


@frappe.whitelist()
def bulk_assign_verifications(verifier, count=0, filters=None, verification_names=None):
    from frappe import _
    import json
    from slcm.pace.doctype.pace_document_verification.get_document_api import generate_document_verification
    
    if not verifier:
        frappe.throw(_("Please select a verifier."))
    
    targets = []
    if verification_names:
        if isinstance(verification_names, str):
            verification_names = json.loads(verification_names)
        targets = verification_names
    elif count:
        count = int(count)
        if count <= 0:
            frappe.throw(_("Please specify a valid count."))
            
        if filters and isinstance(filters, str):
            filters = json.loads(filters)
        
        # Fetch matching unassigned verifications
        filters = filters or {}
        filters.update({
            "assigned_verifier": ["in", ["", None]]
        })
        
        records = frappe.get_all("PACE Document Verification", filters=filters, fields=["name", "application"], limit=count)
        targets = [r.name for r in records]
    else:
        frappe.throw(_("Please select verification records or specify a count."))

    assigned_count = 0
    assigned_details = []
    
    for docname in targets:
        # Get application name
        app_name = frappe.db.get_value("PACE Document Verification", docname, "application")
        if app_name:
            # Update Application
            frappe.db.set_value("PACE Application", app_name, "assigned_verifier", verifier)
            
            # Create/Update Verification Record
            generate_document_verification(app_name)
            
            # Collect info for notification
            app_info = frappe.db.get_value("PACE Application", app_name, ["name", "applicant_name", "programme"], as_dict=True)
            if app_info:
                assigned_details.append(app_info)
            
            assigned_count += 1
            
    if assigned_count > 0:
        send_verifier_assignment_notifications(verifier, assigned_details)
            
    return {"status": "success", "assigned_count": assigned_count}

@frappe.whitelist()
def get_verifiers(doctype, txt, searchfield, start, page_len, filters):
    """
    Returns a list of users who can act as verifiers.
    Used by the search link in PACE Document Verification.
    """
    return frappe.db.sql("""
        SELECT DISTINCT parent 
        FROM `tabHas Role` 
        WHERE role IN ('Admission Officer', 'Admission Admin', 'System Manager')
        AND parent LIKE %s
        LIMIT %s OFFSET %s
    """, (f"%{txt}%", page_len, start))

@frappe.whitelist()
def get_unassigned_verifications(filters=None, limit=100):
    import json
    if filters and isinstance(filters, str):
        filters = json.loads(filters)
    
    base_filters = filters or {}
    base_filters.update({
        "assigned_verifier": ["in", ["", None]],
        "overall_status": ["in", ["Pending", "Returned for Correction"]]
    })
    
    records = frappe.get_all("PACE Document Verification", 
        filters=base_filters, 
        fields=["name", "applicant_name", "application"],
        order_by="creation desc",
        limit=int(limit)
    )
    
    return records
