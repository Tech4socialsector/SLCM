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
        return {"status": "success", "sent_count": 0}

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
        # User emails count
        users = frappe.get_all("Has Role", filters={"role": "PACE Applicant"}, fields=["parent"])
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
        count = frappe.db.count("PACE Applicant Fee Assignment", {"status": "Assigned", "fee_type": "Admission Fee"})
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
    
    if total_sent == 0:
        return {
            "status": "success", 
            "message": frappe._("No reminder emails were sent. All eligible recipients have already received their reminders today."), 
            "sent_count": 0
        }

    return {"status": "success", "sent_count": total_sent}
