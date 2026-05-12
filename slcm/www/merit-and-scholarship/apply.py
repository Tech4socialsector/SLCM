import frappe
from frappe import _

no_cache = 1

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
        user_email = frappe.session.user
        applicant = frappe.db.get_value("Applicant", {"email": user_email}, 
            ["name", "candidate_name", "admission_cycle", "campus", "program", "program_level"], as_dict=1)
        
        if not applicant:
            # Fallback 1: check Eligibility Result email
            applicant_id = frappe.db.get_value("Eligibility Result", {"email": user_email}, "applicant_id")
            if applicant_id:
                applicant = frappe.db.get_value("Applicant", applicant_id, 
                    ["name", "candidate_name", "admission_cycle", "campus", "program", "program_level"], as_dict=1)
        
        if not applicant:
            # Fallback 2: search by owner
            applicant = frappe.db.get_value("Applicant", {"owner": user_email}, 
                ["name", "candidate_name", "admission_cycle", "campus", "program", "program_level"], as_dict=1)
        
        if not applicant:
            context.error = _("No applicant record found for your account. Please complete your registration first.")
            return context
            
        context.applicant = applicant

        # Check if Admission Fee is paid (to block direct access)
        # Scholarships should only be blocked if the actual Admission/Program fee is paid,
        # not just the initial Application Fee.
        is_fee_paid = frappe.db.exists("Applicant Fee Assignment", {
            "applicant": applicant.name,
            "admission_cycle": applicant.admission_cycle,
            "fee_type": "Admission Fee",
            "status": ["in", ["Paid", "Converted"]],
            "docstatus": ["!=", 2]
        }) or (frappe.db.get_value("Applicant", applicant.name, "application_status") == "Fee Paid")

        if is_fee_paid:
            context.error = _("Scholarship applications are not permitted once the admission fee has been paid. "
                              "Scholarships must be applied for and approved before final payment is made.")
            return context
        
        # Add portal config for contact details
        from slcm.admission.utils.portal import get_portal_config
        context.portal_config = get_portal_config()

    except frappe.DoesNotExistError:
        context.error = _("The requested scholarship scheme does not exist.")
    except Exception as e:
        frappe.log_error(f"Scholarship Apply Context Error: {e}")
        context.error = _("An unexpected error occurred. Please try again later.")

    return context
