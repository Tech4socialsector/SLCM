import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class ApplicantReminderEmailLog(Document):
    pass


def log_applicant_reminder_email(
    recipient, subject, reminder_type,
    status="Sent", sender=None,
    reference_doctype=None, reference_name=None,
    email_template=None, error_log=None
):
    """
    Creates a log entry in Applicant Reminder Email Log.
    Safe to call anywhere — failures are silently logged to Error Log.
    """
    try:
        # Validate reminder_type against allowed options
        options = frappe.get_meta("Applicant Reminder Email Log").get_field("reminder_type").options or ""
        allowed_types = [t.strip() for t in options.split("\n") if t.strip()]
        if reminder_type not in allowed_types:
            reminder_type = allowed_types[0] if allowed_types else "Not Started Application Reminder"

        # Resolve email account from template if provided
        email_account = None
        if email_template and frappe.db.exists("Email Template", email_template):
            email_account = frappe.db.get_value("Email Template", email_template, "email_account")

        # Validate dynamic link reference to avoid insertion errors
        if reference_doctype and reference_name:
            if not frappe.db.exists(reference_doctype, reference_name):
                reference_doctype = None
                reference_name = None

        frappe.get_doc({
            "doctype": "Applicant Reminder Email Log",
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
            "error_log": error_log,
        }).insert(ignore_permissions=True)

        frappe.db.commit()

    except Exception:
        # Never let logging break the main reminder flow
        frappe.log_error(frappe.get_traceback(), "Applicant Reminder Logging Failed")
