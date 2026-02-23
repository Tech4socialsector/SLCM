import frappe
from slcm.admission.doctype.admission_result.admission_result import get_applicant_data

def get_context(context):
    """
    Provides data to the admission_dashboard.html template.
    """
    if frappe.session.user == "Guest":
        context.unauthorized = True
        return context

    data = get_applicant_data()
    
    if isinstance(data, dict) and "error" in data:
        context.error = data["error"]
    else:
        # We might have multiple profiles, but usually just one.
        context.applicant_data = data

    return context
