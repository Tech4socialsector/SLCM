import frappe
from frappe import _


def get_context(context):
    """Pass admission cycle and academic year options to the web form context."""
    pass


def after_save(doc, context):
    """
    Called by Frappe automatically after the web form saves the Applicant document.

    Runs the full eligibility engine on the just-saved Applicant record:
      1. validate_eligibility()  — runs national-test + academic rule checks,
                                    sets doc.evaluation_status and
                                    persists an Eligibility Evaluation record.
      2. Catches frappe.ValidationError (ineligible throw) and re-raises it so
         that the web form shows the ineligibility message to the applicant.
    """
    try:
        # Reload full document to get all child tables (categories, ug_degree_details etc.)
        full_doc = frappe.get_doc("Applicant", doc.name)
        full_doc.validate_eligibility()
    except frappe.ValidationError:
        # Let the ineligibility message bubble up to the web form UI
        raise
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Web Form — Eligibility Check Error")
        raise


@frappe.whitelist()
def check_eligibility(applicant_name):
    """
    Whitelist method called by the web form JS after every key field change.

    Returns a dict:
      {
        "status":  "Eligible" | "Ineligible" | "Incomplete",
        "message": "<html reason string>",
        "program_table_html": "<html>"   # full program comparison table
      }

    The JS uses this to show a coloured toast message without waiting for full save.
    """
    if not applicant_name:
        return {"status": "Incomplete", "message": "", "program_table_html": ""}

    doc = frappe.get_doc("Applicant", applicant_name)

    # Need all four key fields to run a meaningful check
    if not all([doc.program, doc.campus, doc.admission_cycle, doc.academic_year]):
        return {
            "status": "Incomplete",
            "message": _("Please fill in Program, Campus, Admission Cycle and Academic Year to check eligibility."),
            "program_table_html": ""
        }

    try:
        doc.validate_eligibility()
        # If we reach here — eligible (no throw)
        return {
            "status": "Eligible",
            "message": _("You meet the eligibility criteria for the selected program."),
            "program_table_html": doc._build_program_eligibility_html()
        }
    except frappe.ValidationError as e:
        return {
            "status": "Ineligible",
            "message": str(e),
            "program_table_html": ""
        }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Web Form — check_eligibility API Error")
        return {
            "status": "Error",
            "message": _("An error occurred during eligibility check. Please try again."),
            "program_table_html": ""
        }
