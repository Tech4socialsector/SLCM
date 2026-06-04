import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class PACEReminderEmailLog(Document):
    pass

def log_pace_reminder_email(recipient, subject, reminder_type, status="Sent", 
                          sender=None, reference_doctype=None, reference_name=None, 
                          email_template=None, error_log=None):
    """
    Logs an entry into PACE Reminder Email Log.
    """
    try:
        # Get allowed reminder types from the database to avoid validation errors
        allowed_types = frappe.get_meta("PACE Reminder Email Log").get_field("reminder_type").options.split("\n")
        
        # If the requested type is not in the allowed list, map it to a valid one
        if reminder_type not in allowed_types:
            if "Rejection" in reminder_type:
                # Try to use a generic type if rejection isn't available yet
                if "Missing Document" in subject:
                    reminder_type = "Missing Document Reminder"
                elif "Payment" in subject or "Fee" in subject:
                    reminder_type = "Payment Reminder"
                else:
                    reminder_type = "Draft Reminder"
            
            # Final safety check: if still not in allowed_types, use the first available option
            if reminder_type not in allowed_types and allowed_types:
                reminder_type = allowed_types[0]

        email_account = None
        if email_template and frappe.db.exists("Email Template", email_template):
            email_account = frappe.db.get_value("Email Template", email_template, "email_account")

        # Basic validation for reference name to prevent validation errors on Dynamic Link
        if reference_doctype and reference_name:
            if not frappe.db.exists(reference_doctype, reference_name):
                # If reference doesn't exist, don't link it to avoid error
                reference_doctype = None
                reference_name = None

        frappe.get_doc({
            "doctype": "PACE Reminder Email Log",
            "recipient": recipient,
            "sender": sender,
            "subject": subject,
            "reminder_type": reminder_type,
            "status": status,
            "sent_at": now_datetime(),
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "email_template": email_template,
            "email_account": email_account,
            "error_log": error_log
        }).insert(ignore_permissions=True)
        
        frappe.db.commit() 
    except Exception:
        # Avoid breaking the main flow if logging fails
        frappe.log_error(frappe.get_traceback(), "PACE Reminder Logging Failed")
