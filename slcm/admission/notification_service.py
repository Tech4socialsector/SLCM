import frappe
from frappe.utils import now
 
def notify_status_change(applicant, program, old_status, new_status, allocation_name, admission_cycle=None, row=None):
    """
    Sends an email notification to the applicant about a status change
    using the 'Seat Allocation Result Notification' template record and logs it.
    """
    try:
        applicant_doc = frappe.get_doc("Eligibility Result", applicant)
    except frappe.DoesNotExistError:
        frappe.logger().error(f"Notification error: Eligibility Result '{applicant}' not found.")
        return
 
    # Resolve email: Try Eligibility Result first, then fallback to Applicant
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
 
    # Force Candidate Name resolution if missing or None
    raw_name = doc_context.get("candidate_name") or applicant_doc.candidate_name
    if not raw_name and doc_context.get("applicant_id"):
        raw_name = frappe.db.get_value("Applicant", doc_context["applicant_id"], "candidate_name")
    
    # Absolute string fallback
    safe_name = str(raw_name or "Applicant")
    if safe_name == "None":
        safe_name = "Applicant"
        
    doc_context["candidate_name"] = safe_name
    doc_context["applicant_name"] = safe_name

    # Resolve Merit Total Score for context
    merit_total_score = doc_context.get("total_score")
    if merit_total_score is None:
        # Try fetching from Merit List Applicant for this cycle
        merit_total_score = frappe.db.get_value("Merit List Applicant", {
            "applicant": applicant,
            "parentfield": "merit_applicants"
        }, "total_score")
    
    # Format if number
    if merit_total_score is not None:
        try:
            from frappe.utils import flt
            merit_total_score = flt(merit_total_score, 3)
        except:
            pass
    
    doc_context["merit_total_score"] = merit_total_score
    doc_context["total_score"] = merit_total_score

    from frappe.utils import get_url
    
    args = {
        "doc": doc_context,
        "candidate_name": safe_name,
        "applicant_name": safe_name,
        "program": program,
        "admission_cycle": admission_cycle,
        "status": new_status,
        "old_status": old_status,
        "new_status": new_status,
        "allocation_name": allocation_name,
        "merit_total_score": merit_total_score,
        "total_score": merit_total_score,
        "get_url": get_url,
        "base_url": get_url()
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

        # Log specialized communication
        from slcm.admission.utils.notifications import log_communication
        log_communication(
            applicant=applicant,
            communication_type="Email",
            category="Seat Allocation",
            subject=subject,
            content=message,
            reference_doctype="Seat Allocation",
            reference_name=allocation_name
        )
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
    Sends email notifications ONLY to the applicants listed in the 
    Seat Allocation document.
    """
    allocation = frappe.get_doc("Seat Allocation", allocation_name)
    
    if not allocation.selection_applicant:
        frappe.logger().info(f"Notification: No applicants found in {allocation_name}. Skipping.")
        return

    frappe.logger().info(f"Notification: Publishing {allocation_name}. Notifying {len(allocation.selection_applicant)} applicants.")
 
    for row in allocation.selection_applicant:
        notify_status_change(
            applicant=row.applicant_id,
            program=row.program,
            old_status="Draft",
            new_status=row.selection_status,
            allocation_name=allocation_name,
            admission_cycle=allocation.admission_cycle,
            row=row
        )
