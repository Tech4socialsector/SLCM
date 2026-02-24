import frappe
from frappe.utils import now

@frappe.whitelist()
def save_draft(applicant_name, field_data):
    import json
    if isinstance(field_data, str):
        field_data = json.loads(field_data)
    applicant = frappe.get_doc("Applicant", applicant_name)
    if applicant.docstatus != 0:
        return {"status": "error", "message": "Application already submitted"}
    for field, value in field_data.items():
        if hasattr(applicant, field):
            setattr(applicant, field, value)
    applicant.save(ignore_permissions=True)
    frappe.db.commit()
    return {
        "status": "success",
        "message": "Draft saved",
        "saved_at": now()
    }

@frappe.whitelist()
def get_draft_status(applicant_name):
    applicant = frappe.db.get_value(
        "Applicant",
        applicant_name,
        ["modified", "application_status", "docstatus"],
        as_dict=True
    )
    return applicant

def auto_save_all_drafts():
    draft_applicants = frappe.get_all(
        "Applicant",
        filters={"docstatus": 0},
        fields=["name", "modified"]
    )
    for applicant in draft_applicants:
        try:
            doc = frappe.get_doc("Applicant", applicant.name)
            doc.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(
                str(e), f"Auto-save failed: {applicant.name}"
            )
    frappe.db.commit()