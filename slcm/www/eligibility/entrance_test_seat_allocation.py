import frappe
from frappe import _
from frappe.utils import format_datetime, get_url

def get_context(context):
    from slcm.admission.utils.portal import get_portal_config
    context.portal_config = get_portal_config()
    
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please login to view this page"), frappe.PermissionError)

    # Get applicant name for the current user
    applicant_name = frappe.db.get_value("Applicant", {"email": user}, "name")
    if not applicant_name:
        context.no_record = True
        return context

    # Get Seat Allocation record name directly without wasted full field query
    allocation_name = frappe.db.get_value(
        "Entrance Test Seat Allocation", 
        {"applicant": applicant_name},
        "name",
        order_by="creation desc"
    )

    if not allocation_name:
        context.no_record = True
        return context

    doc = frappe.get_doc("Entrance Test Seat Allocation", allocation_name)
    context.doc = doc
    
    # Check if rescheduled
    is_rescheduled = (doc.is_rescheduled == 1 or doc.entrance_test_status == "Rescheduled")
    context.is_rescheduled = is_rescheduled
    
    # Track previous schedule if rescheduled
    if is_rescheduled:
        context.previous_schedule = {
            "center": doc.center_name,
            "address": doc.center_address,
            "date": doc.allocation_date,
            "status": doc.allocation_status or "Rescheduled",
            "reason": doc.reschedule_reason or "System Rescheduled"
        }
    else:
        context.previous_schedule = None
    
    # Get preferences
    raw_prefs = doc.re_assigned_preferences if is_rescheduled else doc.assigned_preferences
    context.preferences = []
    for p in raw_prefs:
        context.preferences.append({
            "provider": p.provider,
            "center_name": p.center_name,
            "center_address": p.center_address
        })
    
    # Check if result is published
    context.show_result = (doc.entrance_test_status in ["Attended", "Absent"] and doc.result_published == 1)

    # Entrance test times calculation (reporting time is 45 mins before start time)
    from slcm.admission.utils.portal import get_entrance_test_times
    test_time_str, rep_time_str = get_entrance_test_times(doc)
    context.test_time = test_time_str
    context.reporting_time = rep_time_str
    # Branding & JSON for client-side generation
    campus_branding = {"campus_name": doc.campus or "Institution of Legal Education", "logo": None}
    try:
        if doc.campus:
            campus = frappe.get_doc("Campus", doc.campus)
            campus_branding["campus_name"] = campus.campus_name or doc.campus
            campus_branding["logo"] = campus.logo
    except: pass
    context.campus_branding = campus_branding
    context.doc_json = frappe.as_json(doc.as_dict())
    
    return context

@frappe.whitelist()
def save_provider(allocation_name, selected_provider, is_rescheduled=False):
    """
    Saves the provider choice for the applicant.
    """
    from slcm.admission.doctype.entrance_test_list.entrance_test_list import (
        confirm_applicant_preference, 
        confirm_rescheduled_preference
    )
    
    # Security check: verify ownership
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please login to proceed"), frappe.PermissionError)

    applicant_name = frappe.db.get_value("Applicant", {"email": user}, "name")
    
    # Get data from allocation record
    alloc_data = frappe.db.get_value("Entrance Test Seat Allocation", allocation_name, ["applicant", "email"], as_dict=True)
    
    if not alloc_data:
        frappe.throw(_("Entrance Test Seat Allocation record not found."), frappe.DoesNotExistError)

    is_authorized = False
    
    if applicant_name and alloc_data.applicant == applicant_name:
        is_authorized = True
    elif alloc_data.email and alloc_data.email.strip().lower() == user.strip().lower():
        is_authorized = True
    else:
        user_roles = frappe.get_roles(user)
        if any(role in user_roles for role in ["System Manager", "Entrance Test Admin", "Exam Cell"]):
            is_authorized = True

    if not is_authorized:
        frappe.throw(_("You are not authorized to modify this record."), frappe.PermissionError)
    
    # Validation
    doc = frappe.get_doc("Entrance Test Seat Allocation", allocation_name)
    if isinstance(is_rescheduled, str):
        is_rescheduled = is_rescheduled.lower() == "true"

    prefs = doc.re_assigned_preferences if is_rescheduled else doc.assigned_preferences
    if not any(p.provider == selected_provider for p in prefs):
        frappe.throw(_("Please choose from your assigned preference centers."))

    if is_rescheduled:
        return confirm_rescheduled_preference(allocation_name, selected_provider)
    else:
        return confirm_applicant_preference(allocation_name, selected_provider)

@frappe.whitelist()
def download_admit_card(allocation_name):
    """
    Downloads the Admit Card PDF generated from the 'Admit Card' Print Format.
    Requires authentication and ownership verification.
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please login to proceed"), frappe.PermissionError)

    applicant_name = frappe.db.get_value("Applicant", {"email": user}, "name")
    alloc_data = frappe.db.get_value("Entrance Test Seat Allocation", allocation_name, ["applicant", "email"], as_dict=True)
    
    if not alloc_data:
        frappe.throw(_("Entrance Test Seat Allocation record not found."), frappe.DoesNotExistError)

    is_authorized = False
    if applicant_name and alloc_data.applicant == applicant_name:
        is_authorized = True
    elif alloc_data.email and alloc_data.email.strip().lower() == user.strip().lower():
        is_authorized = True
    else:
        user_roles = frappe.get_roles(user)
        if any(role in user_roles for role in ["System Manager", "Entrance Test Admin", "Exam Cell"]):
            is_authorized = True

    if not is_authorized:
        frappe.throw(_("You are not authorized to access this admit card."), frappe.PermissionError)

    doc = frappe.get_doc("Entrance Test Seat Allocation", allocation_name)
    
    is_rescheduled = (doc.is_rescheduled == 1 or doc.entrance_test_status == "Rescheduled")
    status = doc.re_allocation_status if is_rescheduled else doc.allocation_status
    
    if status not in ["Allocated", "Reallocated"]:
        frappe.throw(_("Admit Card is only available after seat allocation is confirmed."))

    from slcm.admission.doctype.entrance_test_list.entrance_test_list import generate_and_store_admit_card
    stored_file_url = generate_and_store_admit_card(doc.name, is_rescheduled=is_rescheduled)
    
    if stored_file_url:
        frappe.local.response.type = "redirect"
        frappe.local.response.location = stored_file_url
    else:
        frappe.throw(_("Admit Card generation failed. Please ensure the 'Admit Card' Print Format is created in the Desk."))

def get_admit_card_html(doc, is_rescheduled):
    """
    Strictly fetches the Admit Card HTML using the 'Admit Card' Print Format from Desk.
    """
    print_format_name = "Admit Card"
    
    if not frappe.db.exists("Print Format", print_format_name):
        frappe.throw(
            _("Print Format 'Admit Card' not found. Please create it in the Desk and paste the code from sample_admit_card.html."),
            title=_("Configuration Missing")
        )

    return frappe.get_print(
        doc.doctype, 
        doc.name, 
        print_format_name, 
        as_pdf=False, 
        no_letterhead=True
    )
