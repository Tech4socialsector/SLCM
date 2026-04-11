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
        Sync documents and generate PDF.
        """
        self.sync_documents_to_verification()

        doc_before_save = self.get_doc_before_save()
        was_submitted = (doc_before_save.status == "Submitted") if (doc_before_save and hasattr(doc_before_save, 'status')) else False
        if self.status == "Submitted" and not was_submitted:
            frappe.enqueue(
                "slcm.pace.doctype.pace_application.pace_application.process_post_submission",
                doc_name=self.name,
                queue="long"
            )


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
            "self_declaration",
            "passport_oci",
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
    Sends the submission confirmation email using a default Email Template.
    """
    try:
        inst_settings = frappe.get_single("Institution Settings")
        template_name = "PACE Application Submitted"
        
        # Recipient Info
        recipient = doc.email_address
        if not recipient:
            return

        # Prepare arguments for Jinja rendering
        args = {
            "doc": doc,
            "first_name": doc.first_name,
            "candidate_name": f"{doc.first_name} {doc.last_name}",
            "program": doc.programme,
            "applicant_id": doc.name,
            "institution_name": inst_settings.institution_name,
            "admission_portal_url": get_url("/admissions"),
            "generated_on": frappe.utils.format_datetime(frappe.utils.now_datetime(), "dd-MM-yyyy HH:mm:ss")
        }

        # Fetch and render the Email Template
        if not frappe.db.exists("Email Template", template_name):
            frappe.log_error(f"Email Template '{template_name}' not found.", f"Email Error: {doc.name}")
            return

        email_template = frappe.get_doc("Email Template", template_name)
        
        # Render Subject and Message
        subject = frappe.render_template(email_template.subject, args)
        
        # Determine the content field correctly based on 'use_html' toggle
        if email_template.get("use_html"):
            message = frappe.render_template(email_template.response_html, args)
        else:
            message = frappe.render_template(email_template.response, args)

        if not message:
            message = frappe.render_template(email_template.get("message"), args)

        # Get CC from Email Template (added as Custom Field 'cc')
        cc_list = []
        if email_template.cc:
            # Split by comma or semicolon and strip whitespace
            cc_list = [c.strip() for c in email_template.cc.replace(";", ",").split(",") if c.strip()]
        
        # Handle PDF attachment
        attachments = get_application_attachments(doc)

        # Final Email Dispatch
        frappe.sendmail(
            recipients=[recipient],
            cc=cc_list,
            subject=subject,
            content=message,
            attachments=attachments,
            reference_doctype=doc.doctype,
            reference_name=doc.name,
            now=True
        )
        
        # Show success toast to user
        # frappe.msgprint(_("Email sent successfully to {0}").format(recipient), alert=True)
        frappe.log_error(f"Submission email successfully sent to {recipient}", f"Email Success: {doc.name}")

    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"PACE Application Email Failed: {doc.name}")
        # frappe.msgprint(_("Failed to send email. Please check Error Log."), alert=True)

def process_post_submission(doc_name):
    """
    Background job to handle heavy tasks after PACE application submission.
    """
    try:
        doc = frappe.get_doc("PACE Application", doc_name)
        if not doc.application_form:
            doc.generate_application_pdf()
        
        doc.reload()
        send_pace_submission_email(doc)
        send_pace_system_notification(doc)
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"Post Submission Failed: {doc_name}")

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
        "self_declaration",
        "passport_oci",
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
