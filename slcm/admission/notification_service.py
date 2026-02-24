import frappe
from frappe.utils import now

def notify_status_change(applicant, program, old_status, new_status, allocation_name, admission_cycle=None):
    """
    Sends an email notification to the applicant about a status change 
    using the 'Seat Allocation Status' template record and logs it.
    """
    applicant_doc = frappe.get_doc("Admission Result", applicant)

    # Resolve email
    email = getattr(applicant_doc, "email", None) or getattr(applicant_doc, "email_id", None)
    if not email:
        frappe.logger().info(f"Notification skipped: No email found for applicant {applicant}")
        return

    # Fetch and render the Email Template record
    template_name = "Seat Allocation Status"
    if not frappe.db.exists("Email Template", template_name):
        frappe.logger().error(f"Notification error: Email Template '{template_name}' not found.")
        return

    template = frappe.get_doc("Email Template", template_name)
    
    args = {
        "applicant_name": applicant_doc.applicant_name or applicant,
        "program": program,
        "admission_cycle": admission_cycle,
        "status": new_status,
        "old_status": old_status,
        "new_status": new_status,
        "allocation_name": allocation_name
    }

    try:
        subject = frappe.render_template(template.subject, args)
        message = frappe.render_template(template.response, args)
    except Exception as e:
        frappe.logger().error(f"Notification error (Jinja rendering): {e}")
        return

    # Enqueue the email sending with pre-rendered content
    frappe.enqueue(
        method=frappe.sendmail,
        queue="short",
        recipients=[email],
        subject=subject,
        message=message,
        now=frappe.flags.in_test
    )

    # Log to Seat Allocation Audit Log
    from slcm.admission.audit_service import log_seat_allocation_action
    log_seat_allocation_action(
        reference_doctype="Seat Allocation",
        reference_name=allocation_name,
        applicant=applicant,
        program=program,
        action_type="Notification Sent",
        old_value=old_status,
        new_value=new_status,
        remarks=f"Email notification ('{template_name}' template record) sent to {email}."
    )


def notify_published_allocation(allocation_name):
    """
    Sends bulk email notifications to all applicants in a Seat Allocation 
    when it is Published.
    """
    allocation = frappe.get_doc("Seat Allocation", allocation_name)
    
    for row in (allocation.selection_applicant or []):
        notify_status_change(
            applicant=row.applicant,
            program=row.program,
            old_status="Draft",
            new_status=row.selection_status,
            allocation_name=allocation_name,
            admission_cycle=allocation.admission_cycle
        )
