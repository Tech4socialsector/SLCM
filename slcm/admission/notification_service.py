import frappe
from frappe.utils import now
 
def notify_status_change(applicant, program, old_status, new_status, allocation_name, admission_cycle=None, row=None):
    """
    Sends an email notification to the applicant about a status change
    using the 'Seat Allocation Result Notification' template record and logs it.
    """
    try:
        applicant_doc = frappe.get_doc("Admission Result", applicant)
    except frappe.DoesNotExistError:
        frappe.logger().error(f"Notification error: Admission Result '{applicant}' not found.")
        return
 
    # Resolve email: Try Admission Result first, then fallback to Applicant
    email = getattr(applicant_doc, "email", None) or getattr(applicant_doc, "email_id", None)
    
    if not email and applicant_doc.applicant_id:
        email = frappe.db.get_value("Applicant", applicant_doc.applicant_id, "email")
        if email:
            frappe.logger().info(f"Notification: Using fallback email from Applicant {applicant_doc.applicant_id} for {applicant}")
 
    if not email:
        frappe.logger().warning(f"Notification skipped: No email found for applicant {applicant} (ID: {applicant_doc.applicant_id})")
        return
 
    # Fetch and render the Email Template record
    template_name = "Seat Allocation Result Notification"
    if not frappe.db.exists("Email Template", template_name):
        # Fallback to older name if some reason this one isn't there
        template_name = "Seat Allocation Status"
        if not frappe.db.exists("Email Template", template_name):
            frappe.logger().error(f"Notification error: Email Template '{template_name}' not found.")
            return
 
    template = frappe.get_doc("Email Template", template_name)
    
    # Construct combined context for the template (it expects 'doc')
    doc_context = applicant_doc.as_dict()
    if row:
        doc_context.update(row.as_dict())
    else:
        # Fallback fields if called manually without a row
        doc_context.update({
            "selection_status": new_status,
            "program": program,
            "admission_cycle": admission_cycle,
            "applicant": applicant
        })
 
    args = {
        "doc": doc_context,
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
        frappe.logger().error(f"Notification error (Jinja rendering) for {applicant}: {e}")
        return
 
    # Enqueue the email sending with pre-rendered content
    try:
        if frappe.flags.in_test:
            frappe.sendmail(
                recipients=[email],
                subject=subject,
                message=message,
                reference_doctype="Seat Allocation",
                reference_name=allocation_name,
                now=False # Create record but don't try to send via SMTP if we are just testing queue creation
            )
        else:
            frappe.enqueue(
                method=frappe.sendmail,
                queue="short",
                recipients=[email],
                subject=subject,
                message=message,
                reference_doctype="Seat Allocation",
                reference_name=allocation_name,
                now=False
            )
        frappe.logger().info(f"Notification queued: Email to {email} for status {new_status}")
    except Exception as e:
        frappe.logger().error(f"Notification error (enqueue/sendmail) for {applicant}: {e}")
        return
 
    # Log to Admission Audit Log
    try:
        from slcm.admission.doctype.admission_audit_log.audit_service import log_admission_action
        log_admission_action(
            reference_doctype="Seat Allocation",
            reference_name=allocation_name,
            applicant=applicant,
            program=program,
            action_type="Notification Sent",
            old_value=old_status,
            new_value=new_status,
            remarks=f"Email notification ('{template_name}' template record) sent to {email}."
        )
    except ImportError:
        frappe.logger().warning("Notification: Could not import log_admission_action, skipping audit log.")
    except Exception as e:
        frappe.logger().error(f"Notification error (audit log) for {applicant}: {e}")
 
 
def notify_published_allocation(allocation_name):
    """
    Sends bulk email notifications to all applicants in the cycle/campus
    associated with this Seat Allocation when it is Published.
    """
    allocation = frappe.get_doc("Seat Allocation", allocation_name)
    
    # 1. Map existing statuses from the Seat Allocation
    allocated_status_map = {}
    allocated_rows_map = {}
    for row in (allocation.selection_applicant or []):
        allocated_status_map[row.applicant] = row.selection_status
        allocated_rows_map[row.applicant] = row
 
    # 2. Fetch all Admission Results for this cycle and campus
    # This ensures even those NOT in the Merit List (Ineligible etc.) get a notification
    filters = {
        "admission_cycle": allocation.admission_cycle,
        "campus": allocation.campus
    }
    # Filter by program level if the Seat Allocation is specific
    if allocation.program_level:
        filters["program_level"] = allocation.program_level
 
    all_applicants = frappe.get_all("Admission Result", filters=filters, fields=["name", "program"])
 
    frappe.logger().info(f"Notification: Bulk publishing {allocation_name}. Candidates in allocation: {len(allocated_status_map)}, Total applicants to notify: {len(all_applicants)}")
 
    for res in all_applicants:
        status = allocated_status_map.get(res.name)
        row = allocated_rows_map.get(res.name)
        
        if not status:
            # Applicant not in seat allocation (eligibility failed or merit row missing)
            status = "Rejected"
            
        notify_status_change(
            applicant=res.name,
            program=res.program,
            old_status="Draft",
            new_status=status,
            allocation_name=allocation_name,
            admission_cycle=allocation.admission_cycle,
            row=row
        )