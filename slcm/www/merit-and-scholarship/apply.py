import frappe
from frappe import _

def get_context(context):
    scheme_id = frappe.form_dict.get('scheme')
    
    # Redirect back to dashboard if no scheme is provided
    if not scheme_id:
        frappe.local.flags.redirect_location = "/merit-and-scholarship/admission_dashboard"
        raise frappe.Redirect

    if frappe.session.user == "Guest":
        context.unauthorized = True
        return context

    try:
        # Fetch scheme details
        context.scheme = frappe.get_doc("Scholarship Scheme", scheme_id)
        
        # Get applicant details matching the user's email
        applicant = frappe.db.get_value("Applicant", {"email": frappe.session.user}, 
            ["name", "candidate_name", "admission_cycle", "campus", "program", "program_level"], as_dict=1)
        
        if not applicant:
            context.error = _("No applicant record found for your account. Please complete your registration first.")
            return context
            
        context.applicant = applicant
        
        # Add portal config for contact details
        from slcm.admission.utils.portal import get_portal_config
        context.portal_config = get_portal_config()

    except frappe.DoesNotExistError:
        context.error = _("The requested scholarship scheme does not exist.")
    except Exception as e:
        frappe.log_error(f"Scholarship Apply Context Error: {e}")
        context.error = _("An unexpected error occurred. Please try again later.")

    return context
