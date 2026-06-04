import frappe
from frappe.model.document import Document

class PACEReminderEmailConfiguration(Document):
    pass

def is_reminder_enabled(reminder_fieldname):
    """
    Checks if a specific reminder is enabled in the configuration.
    reminder_fieldname: str (e.g., 'enable_application_reminder')
    Returns: bool
    """
    config = frappe.get_single("PACE Reminder Email Configuration")
    return config.get(reminder_fieldname) == "Active"

@frappe.whitelist()
def trigger_manual_reminders(reminders):
    """
    Manually triggers the selected reminder tasks and returns the total count of emails sent.
    'reminders' is a list of fieldnames from the configuration DocType.
    """
    if isinstance(reminders, str):
        import json
        reminders = json.loads(reminders)

    if not reminders:
        return 0

    from slcm.pace.doctype.pace_application.pace_application import (
        send_daily_pace_application_reminders,
        send_payment_reminders,
        send_document_reminders,
        send_correction_reminders
    )
    from slcm.pace.doctype.pace_applicant_fee_assignment.pace_applicant_fee_assignment import send_course_fee_reminders
    from slcm.pace.assignment_logic import check_overdue_verifications

    total_sent = 0
    
    # We run these synchronously to get the count, but we should be careful with large datasets.
    # For now, we follow the requirement to show the count.
    
    if "enable_application_reminder" in reminders or "enable_draft_reminder" in reminders:
        total_sent += (send_daily_pace_application_reminders() or 0)
    
    if "enable_payment_reminder" in reminders:
        total_sent += (send_payment_reminders() or 0)
        
    if "enable_missing_document_reminder" in reminders:
        total_sent += (send_document_reminders() or 0)
        
    if "enable_correction_reminder" in reminders:
        total_sent += (send_correction_reminders() or 0)
        
    if "enable_course_fee_reminder" in reminders:
        total_sent += (send_course_fee_reminders() or 0)
        
    if "enable_verifier_pending_reminder" in reminders or "enable_verifier_overdue_reminder" in reminders:
        total_sent += (check_overdue_verifications() or 0)

    return total_sent
