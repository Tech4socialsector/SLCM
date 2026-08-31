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

def get_reminder_interval(interval_fieldname):
    """
    Gets the interval for a specific reminder from the configuration.
    interval_fieldname: str (e.g., 'application_reminder_interval')
    Returns: int
    """
    config = frappe.get_single("PACE Reminder Email Configuration")
    interval = config.get(interval_fieldname)
    return frappe.utils.cint(interval) if interval is not None else 1

def should_send_reminder(reminder_type, last_sent_date, admission_close_date=None):
    """
    Determines if a reminder should be sent based on interval and admission closing date.
    reminder_type: str (e.g., 'application', 'draft', 'payment', 'missing_document', 'correction', 'course_fee')
    last_sent_date: date or datetime object
    admission_close_date: date or datetime object
    """
    from frappe.utils import today, getdate, date_diff, add_days
    
    config = frappe.get_single("PACE Reminder Email Configuration")
    
    # Map reminder type to config fields
    field_map = {
        "application": ("enable_application_reminder", "application_reminder_interval"),
        "draft": ("enable_draft_reminder", "draft_reminder_interval"),
        "payment": ("enable_payment_reminder", "payment_reminder_interval"),
        "missing_document": ("enable_missing_document_reminder", "missing_document_reminder_interval"),
        "correction": ("enable_correction_reminder", "correction_reminder_interval"),
        "course_fee": ("enable_course_fee_reminder", "course_fee_reminder_interval"),
        "verifier_pending": ("enable_verifier_pending_reminder", "verifier_pending_reminder_interval"),
        "verifier_overdue": ("enable_verifier_overdue_reminder", "verifier_overdue_reminder_interval"),
    }
    
    if reminder_type not in field_map:
        return False
        
    enable_field, interval_field = field_map[reminder_type]
    
    # 1. Status Check: Must be Active
    if config.get(enable_field) != "Active":
        return False
        
    today_date = getdate(today())
    
    # 2. Admission Close Date Exception
    if admission_close_date:
        close_date = getdate(admission_close_date)
        # If today is the close date, send it regardless of interval
        if today_date == close_date:
            # But check if already sent today to avoid spamming
            if last_sent_date and getdate(last_sent_date) == today_date:
                return False
            return True
            
        # If today is after the close date, return True (for rejection logic to use)
        if today_date > close_date:
            return True

    # 3. Same-day Safety Check for normal intervals
    if last_sent_date and getdate(last_sent_date) == today_date:
        return False

    # 4. Interval Check
    if not last_sent_date:
        return True
        
    interval_val = config.get(interval_field)
    interval = frappe.utils.cint(interval_val) if interval_val is not None else 1
    days_since_last_sent = date_diff(today_date, getdate(last_sent_date))
    # Requirement: last sent 17, interval 2, next 20. 
    # Gap of 2 days (18, 19). 20 - 17 = 3. So diff must be > interval.
    # If interval is 0, diff must be > 0 (i.e. at least 1 day since last sent).
    return days_since_last_sent > interval

@frappe.whitelist()
def trigger_manual_reminders(reminders):
    """
    Enqueues the manual reminder task to run in the background.
    """
    if isinstance(reminders, str):
        import json
        reminders = json.loads(reminders)

    if not reminders:
        return {"status": "success", "sent_count": 0}

    frappe.enqueue(
        "slcm.pace.doctype.pace_reminder_email_configuration.pace_reminder_email_configuration.run_manual_reminders_in_background",
        queue="long",
        timeout=3600,
        reminders=reminders,
        user=frappe.session.user
    )
    return {
        "status": "queued",
        "message": frappe._("Reminder emails are being processed in the background. You can safely close or refresh this page. You will receive an alert once completed.")
    }

def run_manual_reminders_in_background(reminders, user):
    """
    Runs the manual reminders in a background worker to avoid timeouts.
    """
    frappe.set_user(user)

    from slcm.pace.doctype.pace_application.pace_application import (
        send_daily_pace_application_reminders,
        send_payment_reminders,
        send_document_reminders,
        send_correction_reminders
    )
    from slcm.pace.doctype.pace_applicant_fee_assignment.pace_applicant_fee_assignment import send_course_fee_reminders
    from slcm.pace.assignment_logic import check_overdue_verifications

    # 1. Pre-calculate total items for progress bar
    tasks_with_counts = []
    total_items = 0

    if "enable_application_reminder" in reminders or "enable_draft_reminder" in reminders:
        users = frappe.get_all("Has Role", filters={"role": "PACE Applicant"}, fields=["parent"], limit=0)
        user_emails = list(set([u.parent for u in users]))
        count = len(user_emails)
        tasks_with_counts.append({"task": send_daily_pace_application_reminders, "count": count})
        total_items += count

    if "enable_payment_reminder" in reminders:
        count = frappe.db.count("PACE Application", {"status": "Submitted"})
        tasks_with_counts.append({"task": send_payment_reminders, "count": count})
        total_items += count

    if "enable_missing_document_reminder" in reminders:
        count = frappe.db.count("PACE Application", {"status": "Provisionally Submitted"})
        tasks_with_counts.append({"task": send_document_reminders, "count": count})
        total_items += count

    if "enable_correction_reminder" in reminders:
        count = frappe.db.count("PACE Application", {"status": "Returned for Correction"})
        tasks_with_counts.append({"task": send_correction_reminders, "count": count})
        total_items += count

    if "enable_course_fee_reminder" in reminders:
        count = frappe.db.count("PACE Applicant Fee Assignment", {"status": "Assigned", "fee_type": "Course Fee"})
        tasks_with_counts.append({"task": send_course_fee_reminders, "count": count})
        total_items += count

    if "enable_verifier_pending_reminder" in reminders or "enable_verifier_overdue_reminder" in reminders:
        count = frappe.db.count("PACE Document Verification", {"status": "Pending"})
        tasks_with_counts.append({"task": check_overdue_verifications, "count": count})
        total_items += count

    # 2. Run tasks and report progress
    total_sent = 0
    current_processed = 0

    for item in tasks_with_counts:
        try:
            task = item["task"]
            count = item["count"]
            
            res = task(current_item=current_processed, total_items=total_items)
            total_sent += (res or 0)
            current_processed += count
            
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Manual Reminder Trigger Failed for {task.__name__}")
    
    # Send final success alert directly to the user via sockets
    frappe.publish_realtime(
        "msgprint",
        {
            "message": frappe._("Background Task Completed: {0} reminder email(s) sent successfully.").format(total_sent) if total_sent > 0 else frappe._("Background Task Completed: No reminder emails were sent. All eligible recipients have already received their reminders today."),
            "title": "PACE Reminders",
            "indicator": "green" if total_sent > 0 else "orange"
        },
        user=user
    )
