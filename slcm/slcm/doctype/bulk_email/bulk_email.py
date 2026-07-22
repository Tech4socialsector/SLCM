import frappe
from frappe.model.document import Document
import json

class BulkEmail(Document):
    pass


@frappe.whitelist()
def create_and_queue(reference_doctype, recipient_names, sender_email_account, subject, cc=None, bcc=None, use_html=0, message=None, message_html=None, attachment=None, email_template=None, filters_applied=None):
    if isinstance(recipient_names, str):
        recipient_names = json.loads(recipient_names)
    
    if not subject:
        frappe.throw("Subject is mandatory")
    
    if not frappe.db.exists("Email Account", {"name": sender_email_account, "enable_outgoing": 1}):
        frappe.throw(f"Email account {sender_email_account} does not exist or outgoing is not enabled")
        
    if not recipient_names:
        frappe.throw("Recipient list is empty")
        
    use_html = int(use_html) if use_html else 0
    if use_html:
        if not message_html:
            frappe.throw("HTML Message cannot be empty")
    else:
        if not message:
            frappe.throw("Message cannot be empty")
            
    email_field = "email" if reference_doctype == "Applicant" else "email_address"
    name_field = "name" if reference_doctype == "Applicant" else "applicant_name"
    
    valid_recipients = []
    docs = frappe.get_all(reference_doctype, filters={"name": ("in", recipient_names)}, fields=["name", name_field, email_field])
    
    for d in docs:
        if d.get(email_field):
            valid_recipients.append({
                "recipient_reference": d.name,
                "recipient_name": d.get(name_field) or d.name,
                "email": d.get(email_field)
            })
            
    if not valid_recipients:
        frappe.throw("No valid emails found for the selected recipients.")
        
    doc = frappe.get_doc({
        "doctype": "Bulk Email",
        "reference_doctype": reference_doctype,
        "sender_email_account": sender_email_account,
        "email_template": email_template,
        "subject": subject,
        "use_html": use_html,
        "message": message,
        "message_html": message_html,
        "cc": cc,
        "bcc": bcc,
        "attachment": attachment,
        "status": "Queued",
        "total_recipients": len(valid_recipients),
        "sent_count": 0,
        "failed_count": 0,
        "filters_applied": filters_applied,
        "triggered_by": frappe.session.user
    })
    
    for r in valid_recipients:
        doc.append("recipients", {
            "reference_doctype": reference_doctype,
            "recipient_reference": r["recipient_reference"],
            "recipient_name": r["recipient_name"],
            "email": r["email"],
            "status": "Pending"
        })
        
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    
    frappe.enqueue("slcm.slcm.doctype.bulk_email.bulk_email.process_bulk_email", queue="short", bulk_email_name=doc.name)
    
    return doc.name


def process_bulk_email(bulk_email_name):
    doc = frappe.get_doc("Bulk Email", bulk_email_name)
    try:
        doc.db_set("status", "In Progress")
        doc.db_set("server_response", f"Job started at {frappe.utils.now()}\n")
        frappe.db.commit()
        
        _send_emails(doc, is_resend=False)
    except Exception:
        doc.db_set("status", "Error")
        doc.db_set("server_response", (doc.server_response or "") + f"\nJOB CRASHED at {frappe.utils.now()}:\n" + frappe.get_traceback())
        frappe.db.commit()
        frappe.log_error(title=f"Bulk Email {bulk_email_name} job failed", message=frappe.get_traceback())
        frappe.publish_realtime("bulk_email_complete", {
            "bulk_email": bulk_email_name, 
            "status": "Error", 
            "crashed": True
        }, user=doc.triggered_by)


@frappe.whitelist()
def resend_failed(bulk_email_name):
    doc = frappe.get_doc("Bulk Email", bulk_email_name)
    if doc.status not in ("Partial", "Error"):
        frappe.throw("Can only resend failed recipients for Partial or Error status.")
        
    doc.db_set("status", "In Progress")
    frappe.db.commit()
    
    frappe.enqueue("slcm.slcm.doctype.bulk_email.bulk_email.process_resend", queue="short", bulk_email_name=bulk_email_name)


def process_resend(bulk_email_name):
    doc = frappe.get_doc("Bulk Email", bulk_email_name)
    try:
        doc.db_set("status", "In Progress")
        doc.db_set("server_response", (doc.server_response or "") + f"\nResend job started at {frappe.utils.now()}\n")
        frappe.db.commit()
        
        _send_emails(doc, is_resend=True)
    except Exception:
        doc.db_set("status", "Error")
        doc.db_set("server_response", (doc.server_response or "") + f"\nJOB CRASHED at {frappe.utils.now()}:\n" + frappe.get_traceback())
        frappe.db.commit()
        frappe.log_error(title=f"Bulk Email {bulk_email_name} resend job failed", message=frappe.get_traceback())
        frappe.publish_realtime("bulk_email_complete", {
            "bulk_email": bulk_email_name, 
            "status": "Error", 
            "crashed": True
        }, user=doc.triggered_by)


def _send_emails(doc, is_resend=False):
    sent = doc.sent_count or 0
    failed = doc.failed_count or 0
    
    if is_resend:
        # Reset failed count since we will try them again
        failed = 0
        for row in doc.recipients:
            if row.status == "Failed":
                row.db_set("status", "Pending")
        frappe.db.commit()
        # Recalculate failed count based on what was previously failed but now is pending? 
        # Actually it's easier to just recalculate at the end.
    
    for row in doc.recipients:
        if row.status == "Pending":
            try:
                attachments = []
                if doc.attachment:
                    file_doc = frappe.get_doc("File", {"file_url": doc.attachment})
                    attachments.append({
                        "fname": file_doc.file_name,
                        "fcontent": file_doc.get_content()
                    })

                sender_account_doc = frappe.get_doc("Email Account", doc.sender_email_account)
                sender_email = sender_account_doc.email_id
                
                frappe.sendmail(
                    recipients=[row.email],
                    sender=sender_email,
                    subject=doc.subject,
                    message=doc.message_html if doc.use_html else doc.message,
                    cc=doc.cc,
                    bcc=doc.bcc,
                    attachments=attachments if attachments else None
                )
                row.status = "Sent"
                row.error_message = None
                sent += 1
            except Exception as e:
                row.status = "Failed"
                row.error_message = frappe.get_traceback()
                failed += 1
                
            row.db_update()
            
            frappe.publish_realtime("bulk_email_progress", {
                "bulk_email": doc.name,
                "sent": sent,
                "failed": failed,
                "total": doc.total_recipients
            }, user=doc.triggered_by)
            
    doc.db_set("sent_count", sent)
    doc.db_set("failed_count", failed)
    
    if sent == 0 and failed == 0:
        final_status = "Error"
    elif failed == 0:
        final_status = "Success"
    elif sent == 0:
        final_status = "Error"
    else:
        final_status = "Partial"
        
    doc.db_set("status", final_status)
    doc.db_set("server_response", (doc.server_response or "") + f"Job completed at {frappe.utils.now()}. Sent: {sent}, Failed: {failed}.\n")
    frappe.db.commit()
    
    frappe.publish_realtime("bulk_email_complete", {
        "bulk_email": doc.name,
        "sent": sent,
        "failed": failed,
        "total": doc.total_recipients,
        "status": final_status
    }, user=doc.triggered_by)

