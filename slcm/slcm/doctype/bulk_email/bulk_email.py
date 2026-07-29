import frappe
from frappe.model.document import Document
import json
import socket

class BulkEmail(Document):
    pass


@frappe.whitelist()
def get_available_fields(reference_doctype):
    meta = frappe.get_meta(reference_doctype)
    exclude_fieldtypes = ["Section Break", "Column Break", "Tab Break", 
        "HTML", "Button", "Table", "Table MultiSelect"]
    fields = [
        {"fieldname": f.fieldname, "label": f.label or f.fieldname}
        for f in meta.fields
        if f.fieldtype not in exclude_fieldtypes and f.fieldname
    ]
    # always include "name" — every doc has it, often the docname/ID
    fields.insert(0, {"fieldname": "name", "label": "ID / Name (docname)"})
    return fields


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
            "status": "Queued"
        })
        
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    
    frappe.enqueue("slcm.slcm.doctype.bulk_email.bulk_email.process_bulk_email", queue="short", timeout=600, bulk_email_name=doc.name)
    
    return doc.name


BATCH_SIZE = 20

def process_bulk_email(bulk_email_name):
    doc = frappe.get_doc("Bulk Email", bulk_email_name)

    if doc.status == "Queued":
        doc.db_set("status", "In Progress")
        doc.db_set("server_response", (doc.server_response or "") + f"\nJob started at {frappe.utils.now()}")
        frappe.db.commit()

    original_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(30)  # seconds — no single socket op waits longer

    try:
        pending_rows = [r for r in doc.recipients if r.status == "Queued"]
        batch = pending_rows[:BATCH_SIZE]

        for row in batch:
            if _is_stop_requested(bulk_email_name):
                doc.reload()
                doc.db_set("status", "Stopped")
                doc.db_set("stop_requested", 0)
                sent_so_far = len([r for r in doc.recipients if r.status == "Sent"])
                remaining_count = len([r for r in doc.recipients if r.status == "Queued"])
                doc.db_set("server_response",
                    (doc.server_response or "") +
                    f"\nStopped by request at {frappe.utils.now()}. "
                    f"{sent_so_far} sent, {remaining_count} still queued.")
                frappe.db.commit()
                return  # do NOT re-enqueue the next batch
            
            _process_single_recipient(doc, row, bulk_email_name)

        doc.reload()
        still_queued = any(r.status == "Queued" for r in doc.recipients)

        if still_queued:
            frappe.enqueue(
                method="slcm.slcm.doctype.bulk_email.bulk_email.process_bulk_email",
                queue="short",
                timeout=600,
                bulk_email_name=bulk_email_name
            )
        else:
            _finalize_job(doc, bulk_email_name)

    except Exception:
        doc.db_set("status", "Error")
        doc.db_set("server_response", (doc.server_response or "") + f"\nJOB CRASHED at {frappe.utils.now()}:\n" + frappe.get_traceback())
        frappe.db.commit()
        frappe.log_error(title=f"Bulk Email {bulk_email_name} job failed", message=frappe.get_traceback())
        frappe.publish_realtime("bulk_email_complete", {"bulk_email": bulk_email_name, "status": "Error", "crashed": True}, user=doc.triggered_by)
    finally:
        socket.setdefaulttimeout(original_timeout)

def _finalize_job(doc, bulk_email_name):
    sent = len([r for r in doc.recipients if r.status == "Sent"])
    failed = len([r for r in doc.recipients if r.status == "Failed"])
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
    doc.db_set("server_response", (doc.server_response or "") + f"\nJob completed at {frappe.utils.now()}. Sent: {sent}, Failed: {failed}.")
    frappe.db.commit()
    frappe.publish_realtime("bulk_email_complete", {"bulk_email": bulk_email_name, "sent": sent, "failed": failed, "total": doc.total_recipients, "status": final_status}, user=doc.triggered_by)


@frappe.whitelist()
def is_job_active(bulk_email_name):
    """Returns True if the job appears genuinely still running 
    (heartbeat within the last 90 seconds)."""
    last_beat = frappe.db.get_value("Bulk Email", bulk_email_name, 
        "last_heartbeat")
    if not last_beat:
        return False
    return (frappe.utils.now_datetime() - last_beat).total_seconds() < 90

@frappe.whitelist()
def resume_sending(bulk_email_name):
    doc = frappe.get_doc("Bulk Email", bulk_email_name)

    if doc.status == "Success":
        frappe.throw("This Bulk Email already completed successfully.")

    if is_job_active(bulk_email_name):
        frappe.throw("This job appears to still be actively sending "
            "(recent activity detected). Please wait a moment and "
            "refresh before resuming.")

    # Reset anything not yet confirmed Sent so it gets picked up again
    reset_count = 0
    for row in doc.recipients:
        if row.status in ("Failed", "Sending"):
            row.status = "Queued"
            row.error_message = None
            row.db_update()
            reset_count += 1
    frappe.db.commit()

    doc.reload()
    doc.db_set("status", "In Progress")
    doc.db_set("stop_requested", 0)
    doc.db_set("server_response",
        (doc.server_response or "") +
        f"\nManually resumed by {frappe.session.user} at "
        f"{frappe.utils.now()}. {reset_count} recipient(s) reset "
        f"for retry.")
    frappe.db.commit()

    frappe.enqueue(
        method="slcm.slcm.doctype.bulk_email.bulk_email.process_bulk_email",
        queue="short", timeout=600, bulk_email_name=bulk_email_name
    )

@frappe.whitelist()
def request_stop(bulk_email_name):
    frappe.db.set_value("Bulk Email", bulk_email_name, "stop_requested", 1)
    frappe.db.commit()

def _is_stop_requested(bulk_email_name):
    return frappe.db.get_value("Bulk Email", bulk_email_name, "stop_requested")

def _process_single_recipient(doc, row, bulk_email_name):
    frappe.db.set_value("Bulk Email", bulk_email_name, 
        "last_heartbeat", frappe.utils.now_datetime(), 
        update_modified=False)
    frappe.db.commit()

    try:
        recipient_doc = frappe.get_doc(doc.reference_doctype, row.recipient_reference)
        context = recipient_doc.as_dict()
        rendered_subject = frappe.render_template(doc.subject, context)
        rendered_message = frappe.render_template(
            doc.message_html if doc.use_html else doc.message, context)
    except Exception:
        row.status = "Failed"
        row.error_message = "Template rendering failed:\n" + frappe.get_traceback()
        row.db_update()
        frappe.db.commit()
        frappe.publish_realtime("bulk_email_row_update", {
            "bulk_email": bulk_email_name,
            "row_name": row.name,
            "recipient_reference": row.recipient_reference,
            "status": "Failed",
            "error_message": row.error_message
        }, user=doc.triggered_by)
        
        doc.reload()
        sent = len([r for r in doc.recipients if r.status == "Sent"])
        failed = len([r for r in doc.recipients if r.status == "Failed"])
        doc.db_set("failed_count", failed)
        frappe.publish_realtime("bulk_email_progress", {
            "bulk_email": bulk_email_name,
            "sent": sent,
            "failed": failed,
            "total": doc.total_recipients
        }, user=doc.triggered_by)
        return

    row.status = "Sending"
    row.db_update()
    frappe.db.commit()
    frappe.publish_realtime("bulk_email_row_update", {
        "bulk_email": bulk_email_name,
        "row_name": row.name,
        "recipient_reference": row.recipient_reference,
        "status": "Sending"
    }, user=doc.triggered_by)

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
            subject=rendered_subject,
            message=rendered_message,
            cc=doc.cc,
            bcc=doc.bcc,
            attachments=attachments if attachments else None,
            now=True
        )
        row.status = "Sent"
        row.error_message = None
    except Exception as e:
        row.status = "Failed"
        row.error_message = "Send failed:\n" + frappe.get_traceback()
        
    row.db_update()
    
    doc.reload()
    sent = len([r for r in doc.recipients if r.status == "Sent"])
    failed = len([r for r in doc.recipients if r.status == "Failed"])
    doc.db_set("sent_count", sent)
    doc.db_set("failed_count", failed)
    frappe.db.commit()
    
    frappe.publish_realtime("bulk_email_row_update", {
        "bulk_email": bulk_email_name,
        "row_name": row.name,
        "recipient_reference": row.recipient_reference,
        "status": row.status,
        "error_message": row.error_message if row.status == "Failed" else None
    }, user=doc.triggered_by)
    
    frappe.publish_realtime("bulk_email_progress", {
        "bulk_email": bulk_email_name,
        "sent": sent,
        "failed": failed,
        "total": doc.total_recipients
    }, user=doc.triggered_by)

