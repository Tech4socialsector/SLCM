import frappe
from frappe import _

def get_context(context):
    from slcm.admission.utils.portal import get_portal_config
    context.portal_config = get_portal_config()
    
    email = frappe.form_dict.get('email')
    mobile = frappe.form_dict.get('mobile')
    
    if not (email or mobile):
        context.error = _("Please provide your Email or Mobile Number to track application status.")
        return

    filters = {}
    if email:
        filters['email'] = email
    if mobile:
        filters['mobile_number'] = mobile

    applicants = frappe.get_all("Applicant", filters=filters, 
                                fields=["name", "candidate_name", "program", "application_status", 
                                        "campus", "academic_year"])
    
    if not applicants:
        context.error = _("No application found for the provided details.")
        return

    # For now, show the latest application if multiple exist
    doc = frappe.get_doc("Applicant", applicants[0].name)
    context.applicant = doc
    
    # Document Status
    context.doc_verification = frappe.db.get_value("Applicant Document", {"applicant": doc.name}, "name")
    if context.doc_verification:
        ad = frappe.get_doc("Applicant Document", context.doc_verification)
        context.documents = ad.documents
