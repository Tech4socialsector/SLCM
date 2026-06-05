import frappe
from frappe.utils import today, getdate
from slcm.pace.doctype.pace_applicant_fee_assignment.pace_applicant_fee_assignment import send_course_fee_reminders
from slcm.pace.doctype.pace_application.pace_application import (
    send_daily_pace_application_reminders,
    send_payment_reminders,
    send_document_reminders,
    send_correction_reminders
)

def verify_rejection(app_name):
    print(f"--- Verifying Rejection for {app_name} ---")
    
    app_doc = frappe.get_doc("PACE Application", app_name)
    admission_close_date = "2026-06-03"
    reason = "Test Rejection Reason"
    
    print("\nCalling send_pace_rejection_email directly...")
    from slcm.pace.doctype.pace_application.pace_application import send_pace_rejection_email
    result = send_pace_rejection_email(app_doc, admission_close_date, reason)
    print(f"Result of send_pace_rejection_email: {result}")
    
    frappe.db.commit()
    
    # Check Logs
    logs = frappe.get_all("PACE Reminder Email Log", 
                          filters={"reference_name": app_name}, 
                          fields=["subject", "creation"], 
                          order_by="creation desc")
    print(f"\nEmail Logs for {app_name}:")
    for log in logs:
        print(f"- {log.subject} at {log.creation}")


if __name__ == "__main__":
    app_name = "PACE-2026-2027-00009"
    # Note: This script needs to be run via 'bench execute' or similar
    verify_rejection(app_name)
