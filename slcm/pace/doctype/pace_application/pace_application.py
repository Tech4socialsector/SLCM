# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.pdf import get_pdf
from frappe.utils import get_url
import traceback
import time
import random
import io
import zipfile
from frappe.utils.file_manager import save_file

class PACEApplication(Document):
    def validate(self):
        self.set_applicant_name()

    def before_save(self):
        """Set submission date when status transitions to Submitted."""
        doc_before_save = self.get_doc_before_save()
        prev_status = (doc_before_save.status if doc_before_save and hasattr(doc_before_save, "status") else None)

        if self.status == "Submitted" and prev_status != "Submitted":
            if not self.submission_date:
                self.submission_date = frappe.utils.today()

    def set_applicant_name(self):
        """Populate applicant_name from first, middle, and last names."""
        name_parts = [self.first_name, self.middle_name, self.last_name]
        full_name = " ".join([p for p in name_parts if p]).strip()
        # Remove any double spaces
        while "  " in full_name:
            full_name = full_name.replace("  ", " ")
        self.applicant_name = full_name

    def autoname(self):
        from frappe.model.naming import make_autoname
        # Incremental serial number with random-like unique padding
        # Format example: PACE-2024-00001
        year = self.academic_year or frappe.utils.now_datetime().year
        self.name = make_autoname(f"PACE-{year}-.#####")
		

    def on_update(self):
        """
        Sync documents, generate PDF, and on status change to Submitted:
        send confirmation email directly (no background worker dependency).
        """
        self.sync_documents_to_verification()

        # Generate the application PDF only when the status is "Draft" or "Submitted"
        if self.status in ["Draft", "Submitted"] and not self.flags.get("in_pdf_generation"):
            self.generate_application_pdf()

        doc_before_save = self.get_doc_before_save()
        prev_status = (doc_before_save.status if doc_before_save and hasattr(doc_before_save, 'status') else None)

        # Fire every time status IS 'Submitted' and (it just changed OR verification record is missing)
        verification_exists = frappe.db.exists("PACE Document Verification", {"application": self.name})
        if self.status == "Submitted" and (prev_status != "Submitted" or not verification_exists):
            # Send email DIRECTLY — returns True if queued, False if failed
            email_sent = send_pace_submission_email(self)

            # Send in-app system notification directly
            try:
                send_pace_system_notification(self)
            except Exception:
                frappe.log_error(traceback.format_exc(), f"PACE System Notification Failed: {self.name}")

            # Push toast to browser via realtime
            user = self.owner or frappe.session.user or "Administrator"
            frappe.publish_realtime(
                event="pace_email_status",
                message={
                    "status": "success" if email_sent else "error",
                    "doc_name": self.name,
                    "recipient": self.email_address or ""
                },
                user=user
            )

            # Create document verification record synchronously for better reliability
            try:
                from slcm.pace.doctype.pace_document_verification.get_document_api import generate_document_verification
                generate_document_verification(self.name)
            except Exception:
                frappe.log_error(message=traceback.format_exc(), title=f"Post Submission Doc Verification Failed: {self.name}")


    def sync_documents_to_verification(self):
        """
        Sync document files to the verification record if they have changed.
        Also add missing document items if they exist on the application.
        """
        verification_name = frappe.db.get_value("PACE Document Verification", {"application": self.name}, "name")
        if not verification_name:
            return

        verification = frappe.get_doc("PACE Document Verification", verification_name)
        updated = False

        # Identify specific document fields to sync
        verify_fieldnames = [
            "student_signature",
            "ug_degree_certificate",
            "govt_id"
        ]
        
        meta = frappe.get_meta("PACE Application")
        attach_fields = [
            f for f in meta.fields 
            if f.fieldname in verify_fieldnames
        ]

        existing_fieldnames = [row.fieldname for row in verification.verification_items]

        for field in attach_fields:
            current_file = self.get(field.fieldname)

            if field.fieldname in existing_fieldnames:
                # Update existing entry (even if current_file is empty)
                for row in verification.verification_items:
                    if row.fieldname == field.fieldname:
                        if row.file != current_file:
                            row.file = current_file
                            updated = True
                        break
            elif current_file:
                # Add missing entry (only if there is actually a file)
                verification.append("verification_items", {
                    "document_name": field.label,
                    "fieldname": field.fieldname,
                    "file": current_file,
                    "status": "Pending"
                })
                updated = True
        
        if updated:
            verification.save(ignore_permissions=True)

    def generate_application_pdf(self):
        self.flags.in_pdf_generation = True
        try:
            pdf_content = self.get_application_pdf_content()
            if not pdf_content:
                return

            timestamp = int(time.time())
            filename = f"PACE_Application_{self.name}_{timestamp}.pdf"
            
            existing_files = frappe.get_all("File", filters={
                "attached_to_doctype": self.doctype,
                "attached_to_name": self.name,
                "attached_to_field": "application_form"
            })
            
            for f in existing_files:
                frappe.delete_doc("File", f.name, ignore_permissions=True)
            
            _file = frappe.get_doc({
                "doctype": "File",
                "file_name": filename,
                "attached_to_doctype": self.doctype,
                "attached_to_name": self.name,
                "attached_to_field": "application_form",
                "content": pdf_content,
                "is_private": 0
            })
            _file.insert(ignore_permissions=True)
            file_url = _file.file_url
            
            if self.application_form != file_url:
                self.db_set("application_form", file_url, update_modified=False)
                self.application_form = file_url
                
        except Exception:
            frappe.log_error(message=traceback.format_exc(), title=f"PACE Application PDF Generation Failed: {self.name}")
        finally:
            self.flags.in_pdf_generation = False

    def get_application_pdf_content(self):
        print_format_name = "Pace Application Form"
        if not frappe.db.exists("Print Format", print_format_name):
            return None

        return frappe.get_print(
            self.doctype, 
            self.name, 
            print_format_name, 
            as_pdf=True, 
            no_letterhead=True,
            doc=self
        )

def send_pace_submission_email(doc):
    """
    Sends the submission confirmation email using the 'PACE Application Submitted' Email Template.
    Follows the exact same pattern as the working entrance_test_seat_allocation email sender:
      - now=False  → queues to Email Queue (visible in Email Queue list)
      - doc.as_dict() → correct Jinja template rendering
      - message_body guard → never sends blank emails
    Returns True if queued successfully, False otherwise.
    """
    template_name = "PACE Application Submitted"

    # --- 1. Recipient ---
    recipient = doc.email_address
    if not recipient:
        frappe.log_error(
            f"No email_address on {doc.name}. Email skipped.",
            "PACE Email: No Recipient"
        )
        return False

    # --- 2. Institution name (safe) ---
    institution_name = "NLSIU"
    try:
        inst_settings = frappe.get_single("Institution Settings")
        institution_name = inst_settings.institution_name or institution_name
    except Exception:
        pass  # Use fallback silently

    # --- 3. Template args using as_dict() (matches working reference exactly) ---
    doc_dict = doc.as_dict()
    args = {
        "doc": doc_dict,
        "first_name": doc.first_name or "",
        "candidate_name": f"{doc.first_name or ''} {doc.last_name or ''}".strip(),
        "program": doc.programme or "",
        "applicant_id": doc.name,
        "institution_name": institution_name,
        "admission_portal_url": get_url("/admissions"),
        "generated_on": frappe.utils.format_datetime(frappe.utils.now_datetime(), "dd-MM-yyyy HH:mm:ss")
    }

    # --- 4. Load Email Template ---
    if not frappe.db.exists("Email Template", template_name):
        frappe.log_error(
            f"Email Template '{template_name}' not found.",
            f"PACE Email: Template Missing ({doc.name})"
        )
        return False

    email_template = frappe.get_doc("Email Template", template_name)

    # --- 5. Render Subject ---
    try:
        subject = frappe.render_template(email_template.subject or "PACE Application Submitted", args)
    except Exception:
        subject = "PACE Application Submitted"

    # --- 6. Render Message body (matches working reference pattern exactly) ---
    message_body = ""
    try:
        if email_template.get("use_html") and email_template.get("response_html"):
            message_body = frappe.render_template(email_template.response_html, args)
        elif email_template.get("response"):
            message_body = frappe.render_template(email_template.response, args)

        if not message_body:
            message_body = frappe.render_template(email_template.get("message") or "", args)
    except Exception:
        frappe.log_error(traceback.format_exc(), f"PACE Email: Body render failed ({doc.name})")

    # Built-in fallback — never skip email due to bad template
    if not message_body:
        message_body = (
            f"<p>Dear {args['first_name']},</p>"
            f"<p>Your PACE application <strong>{doc.name}</strong> for "
            f"<strong>{args['program']}</strong> has been successfully submitted.</p>"
            f"<p>You can track your application at: "
            f"<a href='{args['admission_portal_url']}'>Admissions Portal</a></p>"
            f"<p>Regards,<br>{institution_name}</p>"
        )

    # --- 7. CC list (safe access, matches reference exactly) ---
    cc_list = []
    cc_field_value = email_template.get("cc")
    if cc_field_value:
        cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]

    # --- 8. PDF attachment ---
    attachments = get_application_attachments(doc)

    # --- 9. Send (now=True = sent immediately, avoids background worker delays) ---
    if message_body:
        try:
            # We use now=True to bypass the Email Queue and send directly.
            # This fixes issues where background workers are stalled on the live server.
            frappe.sendmail(
                recipients=[recipient],
                cc=cc_list,
                subject=subject,
                message=message_body,
                attachments=attachments,
                reference_doctype=doc.doctype,
                reference_name=doc.name,
                now=True
            )
            
            # Log successful dispatch
            frappe.logger().info(f"PACE Submission Email sent successfully to {recipient} for {doc.name}")
            return True
            
        except Exception:
            # If immediate sending fails (e.g. SMTP timeout), log it and fallback to Queueing
            # This ensures the user's application submission doesn't fail just because the email failed.
            frappe.log_error(
                traceback.format_exc(),
                f"PACE Email Immediate Dispatch Failed (Fallback to Queue): {doc.name}"
            )
            
            try:
                # Fallback: at least it stays in the queue to be retried later
                frappe.sendmail(
                    recipients=[recipient],
                    cc=cc_list,
                    subject=subject,
                    message=message_body,
                    attachments=attachments,
                    reference_doctype=doc.doctype,
                    reference_name=doc.name,
                    now=False
                )
            except Exception:
                pass # Already logged the main failure

            return False

    frappe.log_error(
        f"message_body was empty, email NOT sent for {doc.name}",
        f"PACE Email: Empty Body ({doc.name})"
    )
    return False

def process_post_submission(doc_name):
    """
    Background job (default queue) — handles document verification after submission.
    Email and system notification are sent directly in on_update (not here).
    """
    try:
        from slcm.pace.doctype.pace_document_verification.get_document_api import generate_document_verification
        generate_document_verification(doc_name)
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"Post Submission Doc Verification Failed: {doc_name}")

def send_pace_system_notification(doc):
    """
    Creates a Notification Log entry for the applicant in the system portal.
    """
    try:
        recipient = doc.email_address
        if not recipient:
            return

        # Check if the user exists in the system (email is usually the User ID)
        if frappe.db.exists("User", recipient):
            message_body = f"""
                <p>Your application to <strong>National Law School of India University (NLSIU)</strong> for the <strong>{doc.programme} (PACE)</strong> has been successfully submitted.</p>
                <p>Application Reference: <strong>{doc.name}</strong></p>
                <p><a href="/admissions" style="color: #920c24; font-weight: bold;">Click here to track your application.</a></p>
            """
            
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": "PACE Application Submitted",
                "for_user": recipient,
                "type": "Alert",
                "email_content": message_body,
                "document_type": doc.doctype,
                "document_name": doc.name,
                "from_user": frappe.session.user or "Administrator",
                "link": "/admissions"
            }).insert(ignore_permissions=True)
            
            frappe.log_error(f"System notification created for {recipient}", f"Notification Success: {doc.name}")

    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"PACE System Notification Failed: {doc.name}")

def get_application_attachments(doc):
    """
    Helper function to get the PDF attachment.
    """
    attachments = []
    if doc.application_form:
        file_name = frappe.db.get_value("File", {"file_url": doc.application_form}, "name")
        if file_name:
            file_doc = frappe.get_doc("File", file_name)
            attachments.append({
                "fname": file_doc.file_name,
                "fcontent": file_doc.get_content()
            })
    return attachments

@frappe.whitelist()
def bulk_download_attachments(names):
    """
    Creates a ZIP archive containing all attachments for the selected PACE Applications.
    Each application's files are placed in a sub-folder.
    """
    if isinstance(names, str):
        names = frappe.parse_json(names)

    if not names:
        frappe.throw(_("Please select at least one application to download."))

    zip_buffer = io.BytesIO()
    found_files = 0
    
    # List of fields that contain attachments
    attachment_fields = [
        "upload_student_photo",
        "student_signature",
        "ug_degree_certificate",
        "govt_id",
        "application_form"
    ]

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for name in names:
            doc = frappe.get_doc("PACE Application", name)
            # Create a safe folder name for this application
            folder_name = f"{doc.first_name}_{doc.last_name}_{doc.name}".replace(" ", "_")
            
            for field in attachment_fields:
                file_url = getattr(doc, field)
                if not file_url:
                    continue
                
                # Get the File record to retrieve content and real filename
                file_record_name = frappe.db.get_value("File", {
                    "file_url": file_url,
                    "attached_to_doctype": "PACE Application",
                    "attached_to_name": name
                }, "name")
                
                if not file_record_name:
                    # Fallback if not directly attached to this field but exists in DB
                    file_record_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
                
                if file_record_name:
                    file_doc = frappe.get_doc("File", file_record_name)
                    content = file_doc.get_content()
                    if content:
                        # Path inside the ZIP
                        arcname = f"{folder_name}/{file_doc.file_name}"
                        zip_file.writestr(arcname, content)
                        found_files += 1

    if found_files == 0:
        frappe.throw(_("No attachments found for the selected records."))

    zip_buffer.seek(0)
    zip_filename = f"PACE_Attachments_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"
    
    _file = save_file(
        zip_filename,
        zip_buffer.getvalue(),
        "PACE Application",
        names[0], # Attach to the first selected record arbitrarily for storage
        is_private=1
    )
    
    return _file.file_url
