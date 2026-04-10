# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.pdf import get_pdf
from frappe.utils import get_url
import traceback
import time

class PACEApplication(Document):
    def on_update(self):
        """
        Generate and store the Application Form PDF.
        """
        # 1. Always ensure the PDF is up to date
        if not self.flags.in_pdf_generation:
            self.generate_application_pdf()
        
        # 2. Check for status transition to 'Submitted' (the field value)
        # We use get_doc_before_save() to reliably detect if the status just changed
        doc_before_save = self.get_doc_before_save()
        was_submitted = (doc_before_save.status == "Submitted") if (doc_before_save and hasattr(doc_before_save, 'status')) else False
        
        if self.status == "Submitted" and not was_submitted:
            # Force generate PDF if not present to ensure attachment works
            if not self.application_form:
                self.generate_application_pdf()
            
            # Re-load to get the updated application_form field if it was just set
            self.reload()
            
            # Trigger email with default template
            send_pace_submission_email(self)
            
            # Trigger system notification
            send_pace_system_notification(self)

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
            frappe.msgprint(_("No email address found. Email not sent."), alert=True)
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

        # Get CC from Email Template
        cc_list = []
        for fieldname in ["cc", "cc_to", "cc_address"]:
            if email_template.get(fieldname):
                cc_list.append(email_template.get(fieldname))
        
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
        frappe.msgprint(_("Email sent successfully to {0}").format(recipient), alert=True)
        frappe.log_error(f"Submission email successfully sent to {recipient}", f"Email Success: {doc.name}")

    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"PACE Application Email Failed: {doc.name}")
        frappe.msgprint(_("Failed to send email. Please check Error Log."), alert=True)

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
