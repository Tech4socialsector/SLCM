import frappe
from frappe import _

no_cache = 1

def get_context(context):
    from slcm.admission.utils.portal import get_portal_config
    context.portal_config = get_portal_config()
    
    name = frappe.form_dict.get('name')
    email = frappe.form_dict.get('email')
    mobile = frappe.form_dict.get('mobile')
    
    # If no params, and user is logged in, try to find their application
    if not (name or email or mobile) and frappe.session.user != "Guest":
        email = frappe.session.user

    if not (name or email or mobile):
        context.error = _("Please provide your Application Number, Email, or Mobile Number to track status.")
        return

    filters = {}
    if name:
        filters['name'] = name
    if email:
        filters['email'] = email
    if mobile:
        filters['mobile_number'] = mobile

    applicants = frappe.get_all("Applicant", filters=filters, 
                                fields=["name", "candidate_name", "program", "application_status", 
                                        "campus", "academic_year", 
                                        "first_preference", "second_preference", "third_preference"],
                                order_by="creation desc")
    
    if not applicants:
        context.error = _("No application found for the provided details.")
        return

    # Use the first applicant object directly
    context.applicant = applicants[0]
    
    # Document Status
    context.doc_verification = frappe.db.get_value("Applicant Document", {"applicant": context.applicant.name}, "name")
    if context.doc_verification:
        ad = frappe.get_doc("Applicant Document", context.doc_verification)
        context.documents = ad.documents
