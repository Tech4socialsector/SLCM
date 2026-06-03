# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.pdf import get_pdf
from frappe.utils import cint, get_url
import traceback
import time
import random
import io
import os
import zipfile
from frappe.utils.file_manager import save_file

class PACEApplication(Document):
    def validate(self):
        self.set_applicant_name()
        self.validate_ug_degree_rows()
        self.validate_ug_certificate()
        self.validate_single_application_per_year()

    def validate_single_application_per_year(self):
        """
        Enforce that an applicant can only have ONE application per academic year,
        unless 'allow_multiple_application_per_applicant' is checked in the PACE Admission.
        """
        if not self.email_address or not self.academic_year:
            return

        # 1. Check if PACE Admission allows multiple applications for this academic year
        allow_multiple = frappe.db.get_value(
            "PACE Admission",
            {"academic_year": self.academic_year, "status": "Active"},
            "allow_multiple_application_per_applicant"
        )
        
        # Fallback to any admission for that year if no active one is found
        if allow_multiple is None:
            allow_multiple = frappe.db.get_value(
                "PACE Admission",
                {"academic_year": self.academic_year},
                "allow_multiple_application_per_applicant"
            )

        if allow_multiple:
            return

        # 2. Check if any other application exists for the same email and same academic year
        # that is NOT the current record.
        existing = frappe.db.get_value(
            "PACE Application",
            {
                "email_address": self.email_address,
                "academic_year": self.academic_year,
                "name": ["!=", self.name],
                "status": ["!=", "Cancelled"]
            },
            "name"
        )

        if existing:
            frappe.throw(
                _("You have already submitted an application ({0}) for the {1} academic year. Only one application is allowed per academic year.").format(
                    existing, self.academic_year
                ),
                title=_("Duplicate Application")
            )

    def validate_ug_degree_rows(self):
        """Portal web form does not always enforce child-table reqd; enforce here."""
        if getattr(self, "flags", None) and (
            self.flags.get("ignore_validate") or self.flags.get("ignore_mandatory")
        ):
            return

        rows = self.get("ug_degree") or []
        if not rows:
            frappe.throw(
                _("Please add at least one UG Degree entry."),
                title=_("Education Details"),
            )

        for i, row in enumerate(rows, start=1):
            if not (getattr(row, "institution_name", None) or "").strip():
                frappe.throw(_("UG Degree row {0}: Institution Name is mandatory").format(i))
            if not (getattr(row, "university", None) or "").strip():
                frappe.throw(_("UG Degree row {0}: University is mandatory").format(i))
            if not (getattr(row, "programme_studied", None) or "").strip():
                frappe.throw(_("UG Degree row {0}: Programme Studied is mandatory").format(i))
            yp = getattr(row, "year_of_passing", None)
            if yp is None or yp == "" or cint(yp) <= 0:
                frappe.throw(_("UG Degree row {0}: Year of Passing is mandatory").format(i))
            yi = cint(yp)
            if yi < 1000 or yi > 9999:
                frappe.throw(
                    _("UG Degree row {0}: Year of Passing must be exactly 4 digits (1000–9999).").format(i)
                )
            rs = (getattr(row, "result_status", None) or "").strip()
            if not rs:
                frappe.throw(_("UG Degree row {0}: Result Status is mandatory").format(i))
            if rs == "Declared":
                if not (getattr(row, "marking_scheme", None) or "").strip():
                    frappe.throw(
                        _(
                            "UG Degree row {0}: Marking Scheme is mandatory when Result Status is Declared"
                        ).format(i)
                    )
                pct = getattr(row, "obtained_percentagecgpa", None)
                if pct is None or pct == "":
                    frappe.throw(
                        _(
                            "UG Degree row {0}: Obtained Percentage/CGPA is mandatory when Result Status is Declared"
                        ).format(i)
                    )

    def validate_ug_certificate(self):
        """UG Degree Certificate attachment check.

        TEMPORARY: always require the certificate when not Draft.
        Original logic (Declared vs Waiting for result only) is kept in comments below.
        """
        if self.status not in ["Draft"]:
            if not self.ug_degree_certificate:
                frappe.throw(
                    _("UG Degree Certificate is mandatory."),
                    title=_("Mandatory Document Missing"),
                )

        # --- ORIGINAL (result status) — restore when removing TEMP above ---
        # waiting = any(row.result_status == "Waiting for result" for row in self.get("ug_degree") or [])
        # declared = any(row.result_status == "Declared" for row in self.get("ug_degree") or [])
        # if declared and not waiting and self.status not in ["Draft"]:
        #     if not self.ug_degree_certificate:
        #         frappe.throw(
        #             _("UG Degree Certificate is mandatory since result status is 'Declared'."),
        #             title=_("Mandatory Document Missing"),
        #         )

    def before_save(self):
        """Set submission date when status transitions to Submitted or Completed."""
        doc_before_save = self.get_doc_before_save()
        prev_status = (doc_before_save.status if doc_before_save and hasattr(doc_before_save, "status") else None)

        if self.status in ["Submitted", "Completed"] and prev_status not in ["Submitted", "Completed"]:
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
        Sync documents, generate PDF, and on status change to Submitted/Completed:
        send confirmation email directly (no background worker dependency).
        """
        self.sync_user_profile()
        self.sync_documents_to_verification()

        # Generate the application PDF when the status is "Draft", "Submitted", or "Completed"
        if self.status in ["Draft", "Submitted", "Completed"] and not self.flags.get("in_pdf_generation"):
            self.generate_application_pdf()

        doc_before_save = self.get_doc_before_save()
        prev_status = (doc_before_save.status if doc_before_save and hasattr(doc_before_save, 'status') else None)

        # Fire when status is Submitted (for email/notification) or Completed (for verification)
        # and (it just changed OR verification record is missing)
        verification_exists = frappe.db.exists("PACE Document Verification", {"application": self.name})
        if self.status in ["Submitted", "Completed"] and (prev_status != self.status or not verification_exists):
            
            if self.status == "Submitted":
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
            if self.status == "Completed":
                try:
                    from slcm.pace.doctype.pace_document_verification.get_document_api import (
                        ensure_document_verification_for_completed_application,
                    )
                    ensure_document_verification_for_completed_application(self)
                except Exception:
                    frappe.log_error(message=traceback.format_exc(), title=f"Post Submission Doc Verification Failed: {self.name}")

        # --- Update application_received count and handle seat limit ---
        if self.status in ["Completed"] and prev_status not in ["Completed"]:
            self.update_admission_programme_stats()

    def update_admission_programme_stats(self):
        """
        Increments the application_received count in the PACE Admission Programme child table.
        If the total_seats limit is reached, it closes the programme.
        """
        try:
            from slcm.pace.api import _get_active_pace_admission_name
            pace_admission = _get_active_pace_admission_name(academic_year=self.academic_year)
            if not pace_admission:
                return

            # Find the specific row for this programme
            programme_row = frappe.db.get_value(
                "PACE Admission Programme",
                {"parent": pace_admission, "programme": self.programme},
                ["name", "total_seats", "application_received", "status"],
                as_dict=True
            )

            if programme_row:
                new_received = (programme_row.application_received or 0) + 1
                update_dict = {"application_received": new_received}
                
                # Check if we need to close the programme
                # 0 or None means infinity
                if programme_row.status == "Open" and programme_row.total_seats and programme_row.total_seats > 0:
                    if new_received >= programme_row.total_seats:
                        update_dict["status"] = "Closed"
                        frappe.logger().info(f"PACE Admission: Closing programme {self.programme} in {pace_admission} due to seat limit.")

                frappe.db.set_value("PACE Admission Programme", programme_row.name, update_dict)
                frappe.db.commit()

        except Exception:
            frappe.log_error(traceback.format_exc(), f"PACE Application: Failed to update admission stats for {self.name}")

    def sync_user_profile(self):
        if not self.email_address:
            return
            
        user_name = frappe.db.get_value("User", {"email": self.email_address}, "name")
        if not user_name:
            return
            
        user = frappe.get_doc("User", user_name)
        updated = False
        
        if self.first_name and user.first_name != self.first_name:
            user.first_name = self.first_name
            updated = True
            
        if self.last_name is not None and (user.last_name or "") != self.last_name:
            user.last_name = self.last_name
            updated = True
                
        if self.mobile_number and user.mobile_no != self.mobile_number:
            user.mobile_no = self.mobile_number
            updated = True
            
        if self.gender and user.gender != self.gender:
            user.gender = self.gender
            updated = True
            
        from frappe.utils import getdate
        if self.date_of_birth and getdate(user.birth_date) != getdate(self.date_of_birth):
            user.birth_date = self.date_of_birth
            updated = True
            
        if self.country and user.country != self.country:
            user.country = self.country
            updated = True
            
        if self.status in ["Submitted", "Completed"]:
            address_parts = [
                self.address_line_1,
                self.city,
                self.district,
                self.state,
                self.country
            ]
            # Clean up and combine parts into a single line
            address_str = ", ".join([str(p).strip().replace("\n", " ").replace("\r", "") for p in address_parts if p]).strip()
            # Remove any double spaces
            while "  " in address_str:
                address_str = address_str.replace("  ", " ")
                
            if self.pincode:
                address_str += f" - {self.pincode}"
            
            # Update location if field exists on User and has changed
            if hasattr(user, "location") and user.location != address_str:
                user.location = address_str
                updated = True
            
        if updated:
            user.flags.ignore_permissions = True
            user.save(ignore_permissions=True)

    def sync_documents_to_verification(self):
        """
        Sync document files to the verification record if they have changed.
        Also add missing document items if they exist on the application.
        """
        verification_name = frappe.db.get_value("PACE Document Verification", {"application": self.name}, "name")
        if not verification_name:
            return

        verification = frappe.get_doc(
            "PACE Document Verification", verification_name, check_permission=False
        )
        updated = False

        # Identify specific document fields to sync
        verify_fieldnames = [
            "student_signature",
            "ug_degree_certificate",
            "govt_id",
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

    # --- 9. Send (now=False = queued for background sending) ---
    if message_body:
        try:
            # We use now=False to queue the email.
            # This ensures the process is fast and background workers handle the SMTP.
            frappe.sendmail(
                recipients=[recipient],
                sender=get_template_sender(email_template),
                cc=cc_list,
                subject=subject,
                message=message_body,
                attachments=attachments,
                reference_doctype=doc.doctype,
                reference_name=doc.name,
                now=False
            )
            
            # Log successful queueing
            frappe.logger().info(f"PACE Submission Email queued successfully to {recipient} for {doc.name}")
            return True
            
        except Exception:
            frappe.log_error(
                traceback.format_exc(),
                f"PACE Email Queueing Failed: {doc.name}"
            )
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
        from slcm.pace.doctype.pace_document_verification.get_document_api import (
            ensure_document_verification_for_completed_application,
        )
        ensure_document_verification_for_completed_application(doc_name)
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
                <p><a href="/pace_progress_tracker?app={doc.name}" style="color: #920c24; font-weight: bold;">Click here to track your application.</a></p>
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
                "link": f"/pace_progress_tracker?app={doc.name}"
            }).insert(ignore_permissions=True)

    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"PACE System Notification Failed: {doc.name}")


def get_template_sender(template):
    """Helper to resolve the sender email address from an Email Template's email_account field.
    Accepts either an Email Template doc or a template name string.
    """
    if not template:
        return None
    
    email_account = None
    if isinstance(template, str):
        email_account = frappe.db.get_value("Email Template", template, "email_account")
    else:
        email_account = template.get("email_account")

    if email_account:
        return frappe.db.get_value("Email Account", email_account, "email_id") or email_account
    return None

@frappe.whitelist(allow_guest=True)
def get_city_details(city):
    """
    Return state and country for a given city.
    Used by the PACE Application Web Form to auto-fill address details.
    """
    if not city:
        return {}
    return frappe.db.get_value("City", city, ["state", "country"], as_dict=True) or {}

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
def bulk_download_all_records(names):
    """
    Creates a ZIP archive containing ALL uploaded documents for the selected PACE Applications.
    Organized by applicant ID folders.
    Documents included: Photo, Signature, UG Certificate, Govt ID, Application Form, and Admission Letter.
    """
    if isinstance(names, str):
        names = frappe.parse_json(names)

    if not names:
        frappe.throw(_("Please select at least one application to download."))

    zip_buffer = io.BytesIO()
    found_files = 0
    
    # Mapping of fieldnames to professional filenames inside the zip
    document_map = {
        "upload_student_photo": "Student_Photo",
        "student_signature": "Student_Signature",
        "ug_degree_certificate": "UG_Degree_Certificate",
        "govt_id": "Govt_ID",
        "application_form": "Application_Form",
        "admission_letter": "Admission_Letter"
    }

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for name in names:
            doc = frappe.get_doc("PACE Application", name)
            applicant_id = doc.name # e.g. PACE-2024-00001
            applicant_name = doc.applicant_name or "Unknown_Applicant"
            folder_name = f"{applicant_name}-{applicant_id}"
            
            for fieldname, label in document_map.items():
                file_url = getattr(doc, fieldname)
                if not file_url:
                    continue
                
                # Get the File record to retrieve content
                file_record_name = frappe.db.get_value("File", {
                    "file_url": file_url,
                    "attached_to_doctype": "PACE Application",
                    "attached_to_name": name
                }, "name")
                
                if not file_record_name:
                    file_record_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
                
                if file_record_name:
                    file_doc = frappe.get_doc("File", file_record_name)
                    content = file_doc.get_content()
                    if content:
                        # Get original extension
                        ext = os.path.splitext(file_doc.file_name)[1]
                        # Path inside the ZIP: [Applicant Name-Applicant ID] / [Label].[ext]
                        arcname = f"{folder_name}/{label}{ext}"
                        zip_file.writestr(arcname, content)
                        found_files += 1

    if found_files == 0:
        frappe.throw(_("No uploaded documents found for the selected records."))

    zip_buffer.seek(0)
    zip_filename = f"PACE_Bulk_Records_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"
    
    _file = save_file(
        zip_filename,
        zip_buffer.getvalue(),
        "PACE Application",
        names[0],
        is_private=0
    )
    
    return _file.file_url


def send_document_reminders():
    """
    Scheduled task (daily at 10:00 AM) to send reminders for missing documents.
    Criteria:
    - Status is "Completed"
    - Missing any of: upload_student_photo, student_signature, ug_degree_certificate, govt_id
    - Before closing date: Send reminder
    - After closing date: Send rejection and update status
    """
    from frappe.utils import today, date_diff, getdate

    # Get active admission closing date
    from slcm.pace.api import _get_active_pace_admission_name
    pace_admission_name = _get_active_pace_admission_name()
    if not pace_admission_name:
        return

    admission_close_date = frappe.db.get_value("PACE Admission", pace_admission_name, "admission_close_date")
    if not admission_close_date:
        return

    today_date = getdate(today())
    close_date = getdate(admission_close_date)

    # Find applications that are Provisionally Submitted
    applications = frappe.get_all("PACE Application", filters={
        "status": "Provisionally Submitted"
    }, fields=["name", "email_address", "first_name", "last_name", "programme", 
              "student_signature", "ug_degree_certificate", "govt_id", 
              "last_reminder_sent"])

    for app_data in applications:
        # Check for missing documents
        missing = []
        doc_fields = {
            "student_signature": "Student Signature",
            "ug_degree_certificate": "UG Degree Certificate / Semester Marksheet",
            "govt_id": "Govt. ID (Passport for Foreign Nationals)"
        }

        for field, label in doc_fields.items():
            if not app_data.get(field):
                missing.append(label)

        if not missing:
            continue

        app_doc = frappe.get_doc("PACE Application", app_data.name)

        if today_date <= close_date:
            # Send reminder if not already sent today
            if app_data.last_reminder_sent and str(app_data.last_reminder_sent) == str(today()):
                continue
            
            if send_pace_reminder_email(app_doc, missing, admission_close_date):
                send_pace_reminder_system_notification(app_doc, missing, admission_close_date)
                app_doc.db_set("last_reminder_sent", today(), update_modified=False)
        else:
            # After closing date, reject the application.
            # We change the status to "Rejected" so it won't be picked up again tomorrow.
            if send_pace_rejection_email(app_doc, admission_close_date):
                send_pace_rejection_system_notification(app_doc, admission_close_date)
                
                # Update PACE Application Status (using db_set to bypass validation for administrative rejection)
                app_doc.db_set("status", "Rejected")
                
                # Update PACE Document Verification Status if it exists
                verification_name = frappe.db.get_value("PACE Document Verification", {"application": app_doc.name}, "name")
                if verification_name:
                    frappe.db.set_value("PACE Document Verification", verification_name, "status", "Rejected")
                
                frappe.db.commit()

def send_pace_reminder_email(doc, missing_documents, admission_close_date):
    """
    Sends the reminder email using 'PACE Document Reminder Email' template.
    """
    template_name = "PACE Document Reminder Email"
    recipient = doc.email_address
    if not recipient:
        return False

    institution_name = "NLSIU"
    try:
        inst_settings = frappe.get_single("Institution Settings")
        institution_name = inst_settings.institution_name or institution_name
    except Exception:
        pass

    args = {
        "doc": doc.as_dict(),
        "first_name": doc.first_name or "",
        "missing_documents": missing_documents,
        "admission_close_date": frappe.utils.formatdate(admission_close_date),
        "admission_portal_url": get_url("/admissions"),
        "institution_name": institution_name
    }

    if not frappe.db.exists("Email Template", template_name):
        return False

    email_template = frappe.get_doc("Email Template", template_name)
    
    try:
        subject = frappe.render_template(email_template.subject or "Missing Documents Reminder", args)
        
        message_body = ""
        if email_template.get("use_html") and email_template.get("response_html"):
            message_body = frappe.render_template(email_template.response_html, args)
        elif email_template.get("response"):
            message_body = frappe.render_template(email_template.response, args)
        
        if not message_body:
            message_body = frappe.render_template(email_template.get("message") or "", args)

        if message_body:
            frappe.sendmail(
                recipients=[recipient],
                sender=get_template_sender(email_template),
                subject=subject,
                message=message_body,
                reference_doctype=doc.doctype,
                reference_name=doc.name,
                now=False
            )
            return True
    except Exception:
        frappe.log_error(traceback.format_exc(), f"PACE Reminder Email Failed: {doc.name}")
    
    return False

def send_pace_rejection_email(doc, admission_close_date):
    """
    Sends the rejection email after the deadline.
    """
    template_name = "PACE Application Rejected - Missing Documents"
    recipient = doc.email_address
    if not recipient:
        return False

    institution_name = "NLSIU"
    try:
        inst_settings = frappe.get_single("Institution Settings")
        institution_name = inst_settings.institution_name or institution_name
    except Exception:
        pass

    args = {
        "doc": doc.as_dict(),
        "first_name": doc.first_name or "",
        "admission_close_date": frappe.utils.formatdate(admission_close_date),
        "institution_name": institution_name
    }

    if not frappe.db.exists("Email Template", template_name):
        return _send_fallback_rejection_email(doc, args)

    email_template = frappe.get_doc("Email Template", template_name)
    
    try:
        subject = frappe.render_template(email_template.subject or "Application Rejected: Missing Documents", args)
        
        message_body = ""
        if email_template.get("use_html") and email_template.get("response_html"):
            message_body = frappe.render_template(email_template.response_html, args)
        elif email_template.get("response"):
            message_body = frappe.render_template(email_template.response, args)
        
        if not message_body:
            message_body = frappe.render_template(email_template.get("message") or "", args)

        if message_body:
            frappe.sendmail(
                recipients=[recipient],
                sender=get_template_sender(email_template),
                subject=subject,
                message=message_body,
                reference_doctype=doc.doctype,
                reference_name=doc.name,
                now=False
            )
            return True
    except Exception:
        frappe.log_error(traceback.format_exc(), f"PACE Rejection Email Failed: {doc.name}")
    
    return False

def _send_fallback_rejection_email(doc, args):
    """Fallback if Email Template record is missing."""
    subject = f"Application Rejected: Missing Documents - {doc.name}"
    message = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #920c24;">Application Rejected</h2>
            <p>Dear {args['first_name']},</p>
            <p>We regret to inform you that your application for the <strong>{doc.programme}</strong> at <strong>{args['institution_name']}</strong> has been rejected.</p>
            <p>This decision was made because the required documents were not uploaded by the admission closing date ({args['admission_close_date']}), despite previous reminders.</p>
            <p>We wish you the best in your future endeavors.</p>
            <p>Warm regards,<br><strong>Office of Admissions</strong><br>{args['institution_name']}</p>
        </div>
    """
    try:
        frappe.sendmail(
            recipients=[doc.email_address],
            subject=subject,
            message=message,
            reference_doctype=doc.doctype,
            reference_name=doc.name,
            now=False
        )
        return True
    except Exception:
        frappe.log_error(traceback.format_exc(), f"PACE Rejection Fallback Email Failed: {doc.name}")
    return False

def send_pace_reminder_system_notification(doc, missing_documents, admission_close_date):
    """
    Creates a Notification Log entry for missing documents.
    """
    try:
        recipient = doc.email_address
        if not recipient:
            return

        if frappe.db.exists("User", recipient):
            docs_list = "<ul>" + "".join([f"<li>{d}</li>" for d in missing_documents]) + "</ul>"
            formatted_date = frappe.utils.formatdate(admission_close_date)
            message_body = f"""
                <p>Dear {doc.first_name},</p>
                <p>Your application <strong>{doc.name}</strong> is missing the following documents:</p>
                {docs_list}
                <p><strong>Please ensure you upload them before the admission closing date: {formatted_date}.</strong></p>
                <p><a href="/pace_progress_tracker?app={doc.name}" style="color: #920c24; font-weight: bold;">Click here to update your application.</a></p>
            """
            
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": "Missing Documents Reminder",
                "for_user": recipient,
                "type": "Alert",
                "email_content": message_body,
                "document_type": doc.doctype,
                "document_name": doc.name,
                "from_user": frappe.session.user or "Administrator",
                "link": f"/pace_progress_tracker?app={doc.name}"
            }).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"PACE Reminder Notification Failed: {doc.name}")

def send_pace_rejection_system_notification(doc, admission_close_date):
    """
    Creates a Notification Log entry for rejection due to missing documents.
    """
    try:
        recipient = doc.email_address
        if not recipient:
            return

        if frappe.db.exists("User", recipient):
            formatted_date = frappe.utils.formatdate(admission_close_date)
            message_body = f"""
                <p>Dear {doc.first_name},</p>
                <p>Your application <strong>{doc.name}</strong> has been rejected because the required documents were not uploaded by the admission closing date ({formatted_date}).</p>
            """
            
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": "Application Rejected: Missing Documents",
                "for_user": recipient,
                "type": "Alert",
                "email_content": message_body,
                "document_type": doc.doctype,
                "document_name": doc.name,
                "from_user": frappe.session.user or "Administrator",
                "link": f"/pace_progress_tracker?app={doc.name}"
            }).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"PACE Rejection Notification Failed: {doc.name}")

def send_correction_reminders():
    """
    Scheduled task to send reminders for documents returned for correction.
    Criteria:
    - Status is "Returned for Correction"
    - Before closing date: Send reminder
    - After closing date: Send rejection and update status
    """
    from frappe.utils import today, date_diff, getdate

    # Get active admission closing date
    from slcm.pace.api import _get_active_pace_admission_name
    pace_admission_name = _get_active_pace_admission_name()
    if not pace_admission_name:
        return

    admission_close_date = frappe.db.get_value("PACE Admission", pace_admission_name, "admission_close_date")
    if not admission_close_date:
        return

    today_date = getdate(today())
    close_date = getdate(admission_close_date)

    # Find applications that are Returned for Correction
    applications = frappe.get_all("PACE Application", filters={
        "status": "Returned for Correction"
    }, fields=["name", "email_address", "first_name", "last_name", "programme"])

    for app_data in applications:
        # Get the verification record to check last_reminder_sent
        verification_name = frappe.db.get_value("PACE Document Verification", {"application": app_data.name}, "name")
        if not verification_name:
            continue
        
        verification_doc = frappe.get_doc("PACE Document Verification", verification_name)
        app_doc = frappe.get_doc("PACE Application", app_data.name)

        if today_date <= close_date:
            # Send reminder if not already sent today
            if verification_doc.last_reminder_sent and str(verification_doc.last_reminder_sent) == str(today()):
                continue
            
            if send_pace_correction_reminder_email(app_doc, verification_doc, admission_close_date):
                send_pace_correction_reminder_system_notification(app_doc, admission_close_date)
                verification_doc.db_set("last_reminder_sent", today(), update_modified=False)
        else:
            # After closing date, reject the application
            if send_pace_rejection_email(app_doc, admission_close_date):
                send_pace_rejection_system_notification(app_doc, admission_close_date)
                
                # Update PACE Application Status (using db_set to bypass validation for administrative rejection)
                app_doc.db_set("status", "Rejected")
                
                # Update PACE Document Verification Status if it exists
                verification_name = frappe.db.get_value("PACE Document Verification", {"application": app_doc.name}, "name")
                if verification_name:
                    frappe.db.set_value("PACE Document Verification", verification_name, "status", "Rejected")
                
                frappe.db.commit()

def send_pace_correction_reminder_email(doc, verification_doc, admission_close_date):
    """
    Sends the correction reminder email using 'PACE Document Verification Final Update' template.
    """
    template_name = "PACE Document Verification Final Update"
    recipient = doc.email_address
    if not recipient:
        return False

    institution_name = "NLSIU"
    try:
        inst_settings = frappe.get_single("Institution Settings")
        institution_name = inst_settings.institution_name or institution_name
    except Exception:
        pass

    args = {
        "doc": verification_doc,
        "admission_portal_url": get_url("/admissions"),
        "institution_name": institution_name,
        "admission_close_date": frappe.utils.formatdate(admission_close_date)
    }

    if not frappe.db.exists("Email Template", template_name):
        return False

    email_template = frappe.get_doc("Email Template", template_name)
    
    try:
        subject = frappe.render_template(email_template.subject or "Document Correction Required", args)
        
        message_body = ""
        if email_template.get("use_html") and email_template.get("response_html"):
            message_body = frappe.render_template(email_template.response_html, args)
        elif email_template.get("response"):
            message_body = frappe.render_template(email_template.response, args)
        
        if not message_body:
            message_body = frappe.render_template(email_template.get("message") or "", args)

        if message_body:
            frappe.sendmail(
                recipients=[recipient],
                sender=get_template_sender(email_template),
                subject=subject,
                message=message_body,
                reference_doctype="PACE Document Verification",
                reference_name=verification_doc.name,
                now=False
            )
            return True
    except Exception:
        frappe.log_error(traceback.format_exc(), f"PACE Correction Reminder Email Failed: {doc.name}")
    
    return False

def send_pace_correction_reminder_system_notification(doc, admission_close_date):
    """
    Creates a Notification Log entry for document correction.
    """
    try:
        recipient = doc.email_address
        if not recipient:
            return

        if frappe.db.exists("User", recipient):
            formatted_date = frappe.utils.formatdate(admission_close_date)
            message_body = f"""
                <p>Dear {doc.first_name},</p>
                <p>Your application <strong>{doc.name}</strong> still has documents that require correction.</p>
                <p><strong>Please ensure you re-upload them before the admission closing date: {formatted_date}.</strong></p>
                <p><a href="/pace_progress_tracker?app={doc.name}" style="color: #920c24; font-weight: bold;">Click here to update your application.</a></p>
            """
            
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": "Document Correction Reminder",
                "for_user": recipient,
                "type": "Alert",
                "email_content": message_body,
                "document_type": doc.doctype,
                "document_name": doc.name,
                "from_user": frappe.session.user or "Administrator",
                "link": f"/pace_progress_tracker?app={doc.name}"
            }).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"PACE Correction Reminder Notification Failed: {doc.name}")

def send_payment_reminders():
    """
    Scheduled task (daily at 10:00 AM) to send reminders for pending payments.
    Criteria:
    - Status is "Submitted"
    - Before closing date: Send reminder
    """
    from frappe.utils import today, getdate, now_datetime

    # Get active admission closing date
    from slcm.pace.api import _get_active_pace_admission_name
    pace_admission_name = _get_active_pace_admission_name()
    if not pace_admission_name:
        return

    admission_close_date = frappe.db.get_value("PACE Admission", pace_admission_name, "admission_close_date")
    if not admission_close_date:
        return

    today_date = getdate(today())
    close_date = getdate(admission_close_date)

    if today_date > close_date:
        return

    # Find applications that are Submitted
    applications = frappe.get_all("PACE Application", filters={
        "status": "Submitted"
    }, fields=["name", "email_address", "first_name", "last_name", "programme", "application_remainder_sent_on"])

    for app_data in applications:
        # Send reminder if not already sent today
        if app_data.application_remainder_sent_on:
            last_sent_date = getdate(app_data.application_remainder_sent_on)
            if last_sent_date == today_date:
                continue
        
        app_doc = frappe.get_doc("PACE Application", app_data.name)
        if send_pace_payment_reminder_email(app_doc, admission_close_date):
            send_pace_payment_reminder_system_notification(app_doc, admission_close_date)
            app_doc.db_set("application_remainder_sent_on", now_datetime(), update_modified=False)

def send_pace_payment_reminder_email(doc, admission_close_date):
    """
    Sends the payment reminder email using 'Pace Application Completed but Payment Pending' template.
    """
    template_name = "Pace Application Completed but Payment Pending"
    recipient = doc.email_address
    if not recipient:
        return False

    institution_name = "NLSIU"
    try:
        inst_settings = frappe.get_single("Institution Settings")
        institution_name = inst_settings.institution_name or institution_name
    except Exception:
        pass

    args = {
        "doc": doc.as_dict(),
        "first_name": doc.first_name or "",
        "admission_close_date": frappe.utils.formatdate(admission_close_date),
        "admission_portal_url": get_url("/admissions"),
        "institution_name": institution_name
    }

    if not frappe.db.exists("Email Template", template_name):
        return False

    email_template = frappe.get_doc("Email Template", template_name)
    
    try:
        subject = frappe.render_template(email_template.subject or "Payment Pending for Your PACE Application", args)
        
        message_body = ""
        if email_template.get("use_html") and email_template.get("response_html"):
            message_body = frappe.render_template(email_template.response_html, args)
        elif email_template.get("response"):
            message_body = frappe.render_template(email_template.response, args)
        
        if not message_body:
            message_body = frappe.render_template(email_template.get("message") or "", args)

        if message_body:
            frappe.sendmail(
                recipients=[recipient],
                sender=get_template_sender(email_template),
                subject=subject,
                message=message_body,
                reference_doctype=doc.doctype,
                reference_name=doc.name,
                now=False
            )
            return True
    except Exception:
        frappe.log_error(traceback.format_exc(), f"PACE Payment Reminder Email Failed: {doc.name}")
    
    return False

def send_pace_payment_reminder_system_notification(doc, admission_close_date):
    """
    Creates a Notification Log entry for payment pending.
    """
    try:
        recipient = doc.email_address
        if not recipient:
            return

        if frappe.db.exists("User", recipient):
            formatted_date = frappe.utils.formatdate(admission_close_date)
            message_body = f"""
                <p>Dear {doc.first_name},</p>
                <p>Your application <strong>{doc.name}</strong> has been successfully submitted, but the application fee is yet to be received.</p>
                <p>Please complete the payment before the deadline: <strong>{formatted_date}</strong> to avoid any delays.</p>
                <p><a href="/pace_progress_tracker?app={doc.name}" style="color: #920c24; font-weight: bold;">Click here to PAY NOW.</a></p>
            """
            
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": "Payment Pending for Your PACE Application",
                "for_user": recipient,
                "type": "Alert",
                "email_content": message_body,
                "document_type": doc.doctype,
                "document_name": doc.name,
                "from_user": frappe.session.user or "Administrator",
                "link": f"/pace_progress_tracker?app={doc.name}"
            }).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"PACE Payment Reminder Notification Failed: {doc.name}")

def send_daily_pace_application_reminders():
    """
    Scheduled task (daily) to send reminders to PACE Applicants.
    Case 1: Registered but no application.
    Case 2: Application in Draft.
    """
    from frappe.utils import today, getdate, formatdate
    from slcm.pace.api.service.pace_payment import _get_active_pace_admission_name
    
    admission_name = _get_active_pace_admission_name()
    if not admission_name:
        return

    admission_doc = frappe.get_doc("PACE Admission", admission_name)
    if admission_doc.status != "Active" or not admission_doc.admission_close_date:
        return

    today_date = getdate(today())
    close_date = getdate(admission_doc.admission_close_date)

    if today_date > close_date:
        return

    formatted_close_date = formatdate(admission_doc.admission_close_date)

    # Get all users with role "PACE Applicant"
    users = frappe.get_all("Has Role", filters={"role": "PACE Applicant"}, fields=["parent"])
    user_emails = list(set([u.parent for u in users]))
    
    if not user_emails:
        return

    for email in user_emails:
        try:
            # Check for PACE Application
            applications = frappe.get_all("PACE Application", 
                filters={"email_address": email}, 
                fields=["name", "status"]
            )
            
            user_doc = frappe.get_doc("User", email)
            if not user_doc.enabled:
                continue

            if not applications:
                # Case 1: Registered but not started
                # Check if already sent today
                if user_doc.get("last_pace_reminder_sent") == today_date:
                    continue
                
                send_pace_application_reminder_email(user_doc, formatted_close_date)
                user_doc.db_set("last_pace_reminder_sent", today_date, update_modified=False)
            else:
                # Case 2: Check for Draft status
                # Skip users whose applications are submitted/completed
                # We skip the user if they have already successfully submitted or completed at least one application.
                submitted_statuses = [
                    'Fee Paid', 'Provisionally Submitted', 'Enrolled', 'Verified', 
                    'Under Verification', 'Submitted', 'Admitted', 'Completed', 'Converted'
                ]
                
                has_submitted = any(app.status in submitted_statuses for app in applications)
                if has_submitted:
                    # User has at least one in-progress or successful application
                    continue
                
                draft_apps = [app for app in applications if app.status == "Draft"]
                for app in draft_apps:
                    app_doc = frappe.get_doc("PACE Application", app.name)
                    
                    # Check if already sent today
                    if app_doc.draft_application_email_sent_on and getdate(app_doc.draft_application_email_sent_on) == today_date:
                        continue
                        
                    send_pace_draft_reminder_email(app_doc, user_doc, formatted_close_date)
                    app_doc.db_set("draft_application_email_sent_on", frappe.utils.now_datetime(), update_modified=False)
        except Exception:
            frappe.log_error(message=frappe.get_traceback(), title=f"PACE Daily Reminder Failed for {email}")

def send_pace_application_reminder_email(user_doc, admission_close_date):
    """Sends Case 1 reminder email using Email Template doctype."""
    from frappe.email.doctype.email_template.email_template import get_email_template
    
    template_name = "PACE Application Reminder"
    args = {
        "first_name": user_doc.first_name or user_doc.full_name,
        "admission_close_date": admission_close_date
    }
    
    template = get_email_template(template_name, args)
    
    frappe.sendmail(
        recipients=[user_doc.email],
        sender=get_template_sender(template_name),
        subject=template.get("subject") or _("PACE Application Reminder"),
        message=template.get("message"),
        now=True
    )

def send_pace_draft_reminder_email(app_doc, user_doc, admission_close_date):
    """Sends Case 2 reminder email using Email Template doctype."""
    from frappe.email.doctype.email_template.email_template import get_email_template
    
    template_name = "PACE Draft Application Reminder"
    # The template uses {{ doc.application }} as per requirements
    app_doc.application = app_doc.name
    
    args = {
        "doc": app_doc,
        "first_name": user_doc.first_name or user_doc.full_name,
        "admission_close_date": admission_close_date
    }
    
    template = get_email_template(template_name, args)
    
    frappe.sendmail(
        recipients=[user_doc.email],
        sender=get_template_sender(template_name),
        subject=template.get("subject") or _("PACE Draft Application Reminder"),
        message=template.get("message"),
        now=True
    )
