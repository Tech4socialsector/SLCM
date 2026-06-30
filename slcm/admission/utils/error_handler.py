import frappe
from frappe.utils import now

@frappe.whitelist()
def handle_upload_error(applicant_name, document_type, error_message):
    frappe.log_error(
        f"Upload failed for {applicant_name} | "
        f"{document_type} | {error_message}",
        "Document Upload Error"
    )
    return {
        "status": "error",
        "message": "Upload failed. Please try again.",
        "retry": True,
        "support_ref": frappe.generate_hash(length=6).upper()
    }

@frappe.whitelist()
def handle_session_timeout(applicant_name):
    draft_data = frappe.db.get_value(
        "Applicant",
        applicant_name,
        ["modified", "status"],
        as_dict=True
    )
    return {
        "status": "session_expired",
        "last_saved": draft_data.modified if draft_data else None,
        "message": (
            "Your session expired. Your draft has been saved. "
            "Please login again."
        ),
        "redirect": "/login?redirect=/applicant-dashboard"
    }

@frappe.whitelist()
def check_network_status():
    return {
        "status": "online",
        "server_time": now(),
        "message": "Connection restored"
    }

def log_system_error(error_type, error_message, applicant_name=None):
    frappe.log_error(
        f"Type: {error_type} | "
        f"Applicant: {applicant_name} | {error_message}",
        "Admission System Error"
    )