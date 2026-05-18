import frappe
from frappe import _
import json
import traceback
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url, get_datetime, nowdate, format_date, flt, get_site_path
from frappe.utils.pdf import get_pdf
import os
import base64


class EntranceTestSeatAllocation(Document):

    def validate(self):
        max_marks = self.total_marks or 200
        if (self.part_a_total_marks_scored or 0) + (self.part_b_total_marks_scored or 0) > max_marks:
            frappe.throw(f"Total Score (Part A + Part B) cannot be more than {max_marks}.")

    def before_save(self):
        # Calculate total marks and percentage
        self.total_marks_secured_in_part_a_b = (self.part_a_total_marks_scored or 0) + (self.part_b_total_marks_scored or 0)
        
        max_marks = self.total_marks or 200
        if max_marks > 0:
            # Rounding to 2 decimal places as requested
            self.percentage = flt((self.total_marks_secured_in_part_a_b / float(max_marks)) * 100.0, 2)
        else:
            self.percentage = 0

        # Update attendance_marked_on if status changes to Attended, Absent, or Rescheduled
        doc_before = self.get_doc_before_save()
        if not self.is_new():
            if doc_before and self.entrance_test_status != doc_before.entrance_test_status:
                if self.entrance_test_status in ["Attended", "Absent"]:
                    self.attendance_marked_on = now_datetime()

        # Update Applicant's application_status in DB immediately when user changes to Scheduled/Rescheduled/Absent (same transaction = fast, no refresh needed).
        if self.applicant and self.entrance_test_status in ("Scheduled", "Rescheduled", "Absent"):
            status_actually_changed = (
                self.is_new()
                or (doc_before and doc_before.entrance_test_status != self.entrance_test_status)
            )
            if status_actually_changed:
                _update_applicant_status_for_entrance_test_status(
                    self.applicant, self.entrance_test_status
                )

        # Update Applicant's application_status based on Result Status
        if self.applicant and self.result_status:
            status_actually_changed = (
                self.is_new()
                or (doc_before and doc_before.result_status != self.result_status)
            )
            if status_actually_changed:
                _update_applicant_status_for_result_status(self.applicant, self.result_status)

        # Fetch categories from Applicant if newly set or empty
        # Priority: Seat Allocation category (if already filled) vs Applicant's categories
        if self.applicant and (not self.category or self.is_new()):
            from slcm.admission.doctype.applicant.applicant import Applicant
            app_doc = frappe.get_doc("Applicant", self.applicant)
            app_categories = app_doc._get_applicant_categories()
            # Re-initialize the child table ONLY if it's currently empty
            if not self.category:
                for cat in app_categories:
                    self.append("category", {"category": cat})

    def generate_result_card(self):
        """Generates the Entrance Test Result Card PDF using the 'Entrance Test Result Card' print format."""
        try:
            # Using the Print Format name as requested (Configurable way)
            pdf_content = frappe.get_print(
                self.doctype,
                self.name,
                "Entrance Test Result Card",
                as_pdf=True
            )
            
            filename = f"Result_Card_{self.applicant.replace('/', '_')}.pdf"
            _file = frappe.get_doc({
                "doctype": "File",
                "file_name": filename,
                "attached_to_doctype": self.doctype,
                "attached_to_name": self.name,
                "content": pdf_content,
                "is_private": 1
            })
            _file.save(ignore_permissions=True)
            
            self.db_set("entrance_test_result_card", _file.file_url)
            return _file.file_url
            
        except Exception:
            frappe.log_error(traceback.format_exc(), f"Result Card Generation Failed: {self.name}")
            return None


def _update_applicant_status_for_entrance_test_status(applicant_name, entrance_test_status):
    """
    Update Applicant's application_status (Applicant Status doctype) when
    Entrance Test Seat Allocation's entrance_test_status is Scheduled, Rescheduled, or Absent.
    - Scheduled / Rescheduled \u2192 "Entrance Test Scheduled"
    - Absent \u2192 "Entrance Test Rejected"
    """
    status_map = {
        "Scheduled": "Entrance Test Scheduled",
        "Rescheduled": "Entrance Test Scheduled",
        "Absent": "Entrance Test Rejected",
    }
    new_status = status_map.get(entrance_test_status)
    if not new_status:
        return
    if not frappe.db.exists("Applicant Status", new_status):
        frappe.log_error(
            message=f"Applicant Status '{new_status}' does not exist. Create it in Applicant Status doctype.",
            title="Applicant Status Sync Skipped",
        )
        return
    frappe.db.set_value("Applicant", applicant_name, "application_status", new_status)
    frappe.clear_document_cache("Applicant", applicant_name)
    # Notify clients so the Applicant form can auto-refresh if open
    frappe.publish_realtime(
        "applicant_application_status_updated",
        {"docname": applicant_name, "application_status": new_status},
    )

def _update_applicant_status_for_result_status(applicant_name, result_status):
    """
    Update Applicant's application_status (Applicant Status doctype) when
    Entrance Test Seat Allocation's result_status is set.
    - Pass \u2192 "Entrance Test Completed"
    - Fail / Absent / Withheld / Disqualified \u2192 "Entrance Test Rejected"
    """
    new_status = "Entrance Test Completed" if result_status == "Pass" else "Entrance Test Rejected"
    
    if not frappe.db.exists("Applicant Status", new_status):
        frappe.log_error(
            message=f"Applicant Status '{new_status}' does not exist. Create it in Applicant Status doctype.",
            title="Applicant Status Sync Skipped (Result Status)",
        )
        return
    frappe.db.set_value("Applicant", applicant_name, "application_status", new_status)
    frappe.clear_document_cache("Applicant", applicant_name)
    # Notify clients
    frappe.publish_realtime(
        "applicant_application_status_updated",
        {"docname": applicant_name, "application_status": new_status},
    )


@frappe.whitelist()
def bulk_download_admit_cards(names):
    """
    Creates a ZIP archive containing the Admit Cards (PDF)
    for the selected records. Includes both original and rescheduled cards if available.
    """
    import io
    import os
    import zipfile
    from frappe.utils.file_manager import save_file, get_file_path

    if isinstance(names, str):
        names = frappe.parse_json(names)

    if not names:
        frappe.throw("No records selected for download.")

    zip_buffer = io.BytesIO()
    found_files = 0

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for name in names:
            doc = frappe.get_doc("Entrance Test Seat Allocation", name)
            
            # Helper to add file to zip
            def add_to_zip(field, suffix=""):
                nonlocal found_files
                # Ensure the card exists
                if not getattr(doc, field):
                    from slcm.admission.doctype.entrance_test_list.entrance_test_list import generate_and_store_admit_card
                    is_re = (field == "re_admit_card_download")
                    generate_and_store_admit_card(doc, is_rescheduled=is_re)
                    doc.reload()
                
                file_url = getattr(doc, field)
                if file_url:
                    fname = file_url.split('/')[-1]
                    fpath = get_file_path(fname)
                    if os.path.exists(fpath):
                        zip_name = f"Admit_Card_{doc.applicant or doc.name}{suffix}.pdf"
                        zip_file.write(fpath, arcname=zip_name)
                        found_files += 1

            # 1. Process Original Admit Card
            if doc.allocation_status in ["Allocated", "Reallocated"]:
                add_to_zip("admit_card_download")

            # 2. Process Rescheduled Admit Card
            if doc.is_rescheduled and doc.re_allocation_status in ["Allocated", "Reallocated"]:
                add_to_zip("re_admit_card_download", suffix="_Rescheduled")

    if found_files == 0:
        frappe.throw("No Admit Cards found or generated for the selected records (ensure they have an 'Allocated' status).")

    zip_filename = f"Bulk_Admit_Cards_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"
    
    saved_zip = save_file(
        zip_filename,
        zip_buffer.getvalue(),
        "Entrance Test Seat Allocation",
        names[0],
        is_private=0
    )

    return saved_zip.file_url


@frappe.whitelist()
def update_ranks_by_category(academic_year, admission_cycle, program_level, entrance_test_list=None):
    """
    Ranks applicants based on total_marks_secured_in_part_a_b for a given batch and sends result emails.
    Filters: Academic Year, Admission Cycle, Program Level.
    Optional: entrance_test_list
    """
    if not (academic_year and admission_cycle and program_level):
        frappe.throw("Academic Year, Admission Cycle, and Program Level are required for ranking.")

    # 1. Rank Attended applicants
    attended_filters = {
        "academic_year": academic_year,
        "admission_cycle": admission_cycle,
        "program_level": program_level,
        "entrance_test_status": "Attended"
    }
    if entrance_test_list:
        attended_filters["entrance_test_list"] = entrance_test_list

    attended_records = frappe.get_all("Entrance Test Seat Allocation",
        filters=attended_filters,
        fields=["name", "part_a_total_marks_scored", "part_b_total_marks_scored", "total_marks_secured_in_part_a_b"],
        order_by="total_marks_secured_in_part_a_b desc"
    )

    total_attended = len(attended_records)
    if total_attended == 0:
        return 0

    # --- Helper to calculate ranks and percentiles ---
    def calculate_ranks_and_percentiles(records, score_fieldname):
        # Sort by score desc
        sorted_recs = sorted(records, key=lambda x: flt(x.get(score_fieldname)), reverse=True)
        
        results = {}
        last_score = None
        current_rank = 0
        total_students = len(sorted_recs)
        
        for i, rec in enumerate(sorted_recs, start=1):
            score = flt(rec.get(score_fieldname))
            if last_score is None or score != last_score:
                current_rank = i
                last_score = score
            
            # Standard competitive exam percentile logic:
            # Top rank (1) gets 100 percentile.
            # If total_students == 1, they get 100.
            # Same score -> Same Rank -> Same Percentile.
            if total_students <= 1:
                percentile = 100.0
            else:
                percentile = ((total_students - current_rank) / float(total_students - 1)) * 100.0
            
            # Round to 2 decimal places for standard display
            percentile = round(percentile, 2)
            
            results[rec.name] = {
                "rank": current_rank,
                "percentile": percentile
            }
        return results

    # 1.1 Perform ranking passes
    part_a_data = calculate_ranks_and_percentiles(attended_records, "part_a_total_marks_scored")
    part_b_data = calculate_ranks_and_percentiles(attended_records, "part_b_total_marks_scored")
    cumulative_data = calculate_ranks_and_percentiles(attended_records, "total_marks_secured_in_part_a_b")

    # 1.2 Update records (only for attended)
    for i, rec in enumerate(attended_records, start=1):
        rank_a = part_a_data.get(rec.name, {}).get("rank") or 0
        rank_b = part_b_data.get(rec.name, {}).get("rank") or 0
        rank_cum = cumulative_data.get(rec.name, {}).get("rank") or 0
        percentile = cumulative_data.get(rec.name, {}).get("percentile") or 0.0
        
        frappe.db.set_value("Entrance Test Seat Allocation", rec.name, {
            "part_a_all_india_rank": rank_a,
            "part_b_all_india_rank": rank_b,
            "entrance_test_rank": rank_cum,
            "percentile": percentile
        }, update_modified=False)

        # Generate Result Card PDF
        try:
            doc_obj = frappe.get_doc("Entrance Test Seat Allocation", rec.name)
            doc_obj.generate_result_card()
        except Exception:
            frappe.log_error(f"Auto-generation of Result Card failed for {rec.name}")
        
        if i % 10 == 0 or i == total_attended:
            percent = (i / total_attended) * 50
            frappe.publish_progress(percent, title=_("Update Ranking"))

    frappe.db.commit()

    # 1.3 Clear ranks and percentiles for Absent/Non-attended applicants
    absent_filters = attended_filters.copy()
    absent_filters["entrance_test_status"] = ["!=", "Attended"]
    absent_records = frappe.get_all("Entrance Test Seat Allocation", filters=absent_filters, fields=["name"])
    
    for rec in absent_records:
        frappe.db.set_value("Entrance Test Seat Allocation", rec.name, {
            "part_a_all_india_rank": 0,
            "part_b_all_india_rank": 0,
            "entrance_test_rank": 0,
            "percentile": 0.0
        }, update_modified=False)
    
    frappe.db.commit()

    # 2. Fetch ALL applicants (Attended + Absent) to send notifications
    all_filters = {
        "academic_year": academic_year,
        "admission_cycle": admission_cycle,
        "program_level": program_level,
        "entrance_test_status": ["in", ["Attended", "Absent"]]
    }
    if entrance_test_list:
        all_filters["entrance_test_list"] = entrance_test_list

    all_records = frappe.get_all("Entrance Test Seat Allocation",
        filters=all_filters,
        fields=["name", "applicant", "candidate_name", "email", "entrance_test_status", 
                "total_marks_secured_in_part_a_b","entrance_test_rank", "entrance_test_list"]
    )

    count = 0
    total = len(all_records)
    for i, rec in enumerate(all_records):
        percent = 50 + ((float(i + 1) / total) * 50)
        frappe.publish_progress(
            percent, 
            title=_("Update Ranking"), 
            description=f"Notifying {i + 1} of {total}"
        )


        doc = frappe.get_doc("Entrance Test Seat Allocation", rec.name)
        
        # Resolve email
        email = doc.email or ""
        if not email and doc.applicant:
            try:
                app_email = frappe.db.get_value("Applicant", doc.applicant, "email")
                if app_email:
                    email = app_email
            except Exception:
                pass

        if email:
            try:
                _send_result_notification_email(doc, email)
                _send_result_notification(doc, email)
                count += 1
            except Exception:
                frappe.log_error(title=f"Result Email/Notification Failed: {doc.name}")

        if i % 10 == 0:
            frappe.db.commit()

    frappe.db.commit()
    return count


def _send_result_notification_email(doc, email):
    """Send a result/rank notification email to the applicant using a configurable template."""
    try:
        template_name = "Entrance Test Result"
        if not frappe.db.exists("Email Template", template_name):
            frappe.log_error(f"Email Template '{template_name}' not found.", "Email Sending Error")
            return

        template = frappe.get_doc("Email Template", template_name)
        
        # Prepare arguments for Jinja
        doc_dict = doc.as_dict()
        args = {
            "doc": doc_dict,
            "portal_url": get_url("/merit-and-scholarship/admission_dashboard?panel=applications")
        }

        subject = frappe.render_template(template.subject, args)
        
        # Determine the content field correctly
        message_body = ""
        if template.get("use_html"):
            message_body = frappe.render_template(template.response_html, args)
        else:
            message_body = frappe.render_template(template.response, args)

        if not message_body:
            message_body = frappe.render_template(template.get("message") or "", args)
            
        # Robust CC handling from the manual 'cc' field added to Email Template
        cc_list = []
        cc_field_value = template.get("cc")
        if cc_field_value:
            # Split by comma or semicolon, strip whitespace, and filter out empties
            cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]
        
        if message_body:
            attachments = []
            if doc.entrance_test_result_card:
                try:
                    file_doc = frappe.get_doc("File", {"file_url": doc.entrance_test_result_card})
                    attachments.append({
                        "fname": file_doc.file_name,
                        "fcontent": file_doc.get_content()
                    })
                except Exception:
                    pass

            try:
                # Use now=False to queue the email.
                frappe.sendmail(
                    recipients=[email],
                    cc=cc_list,
                    subject=subject,
                    message=message_body,
                    attachments=attachments,
                    reference_doctype="Entrance Test Seat Allocation",
                    reference_name=doc.name,
                    now=False
                )
                frappe.logger().info(f"Entrance Test Notification Email queued successfully to {email} for {doc.name}")
            except Exception:
                frappe.log_error(traceback.format_exc(), f"Entrance Test Notification Email Queueing Failed: {doc.name}")

    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"Result Email Failed: {doc.name}")


@frappe.whitelist()
def reschedule_applicants(applicants, providers, allocation_date, reschedule_reason=None, re_entrance_test_name=None):
    if isinstance(applicants, str):
        applicants = json.loads(applicants)
    if isinstance(providers, str):
        providers = json.loads(providers)

    if not applicants:
        frappe.throw("No applicants selected.")
    if not providers:
        frappe.throw("No providers selected.")
    if not reschedule_reason:
        frappe.throw("Reason for Reschedule is mandatory.")

    # Validate allocation_date is not in the past
    if allocation_date and get_datetime(allocation_date) < now_datetime():
        frappe.throw("New Allocation Date cannot be in the past. Please select today or a future date.")

    # Validate providers
    provider_docs = []
    for pname in providers:
        pdoc = frappe.get_doc("Entrance Test Provider", pname)
        if not pdoc.active:
            frappe.throw(f"Provider '{pname}' is not active.")
        provider_docs.append(pdoc)

    count = 0
    total = len(applicants)
    for i, name in enumerate(applicants):
        # Publish progress
        percent = (float(i + 1) / total * 100)
        frappe.publish_progress(
            percent, 
            title=_("Rescheduling Applicants..."), 
            description=f"Processing {i + 1} of {total}"
        )

        doc = frappe.get_doc("Entrance Test Seat Allocation", name)


        # Update reschedule fields
        doc.is_rescheduled = 1
        doc.re_allocation_date = allocation_date
        doc.re_allocation_status = "Preferences Assigned"
        doc.rescheduled_on = now_datetime()
        doc.rescheduled_by = frappe.session.user
        doc.reschedule_reason = reschedule_reason
        doc.re_entrance_test_name = re_entrance_test_name
        doc.entrance_test_status = "Scheduled"

        # Set re_assigned_preferences
        doc.set("re_assigned_preferences", [])
        for idx, pdoc in enumerate(provider_docs, start=1):
            doc.append("re_assigned_preferences", {
                "provider": pdoc.name,
                "center_name": pdoc.center_name,
                "center_address": pdoc.center_address,
                "preference_order": idx
            })

        doc.save(ignore_permissions=True)

        # \u2500\u2500 Resolve email \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        # Priority: allocation.email \u2192 Applicant doctype email
        email = doc.email or ""
        if not email and doc.applicant:
            # Try fetching from Applicant doctype
            try:
                app_email = frappe.db.get_value("Applicant", doc.applicant, "email")
                if app_email:
                    email = app_email
            except Exception:
                pass

        # \u2500\u2500 Send reschedule notification email \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        if email:
            try:
                _send_reschedule_email(doc, email)
                _send_reschedule_notification(doc, email)
            except Exception:
                frappe.log_error(
                    message=traceback.format_exc(),
                    title=f"Reschedule Email/Notification Failed: {doc.name}"
                )
        else:
            frappe.log_error(
                message=f"No email found for applicant {doc.applicant} (record: {doc.name}). Reschedule email was not sent.",
                title="Reschedule Email Skipped"
            )

        if i % 10 == 0:
            frappe.db.commit()

        count += 1

    frappe.db.commit()
    return count


def _send_reschedule_email(doc, email):
    """Send a reschedule notification email to the applicant using a configurable template."""
    try:
        template_name = "Entrance Test Reschedule"
        if not frappe.db.exists("Email Template", template_name):
            frappe.log_error(f"Email Template '{template_name}' not found.", "Email Sending Error")
            return

        template = frappe.get_doc("Email Template", template_name)
        
        # Prepare arguments for Jinja
        doc_dict = doc.as_dict()
        # Convert child table to list of dicts for Jinja
        doc_dict["re_assigned_preferences"] = [p.as_dict() for p in doc.re_assigned_preferences]
        
        args = {
            "doc": doc_dict,
            "portal_url": get_url("/merit-and-scholarship/admission_dashboard?panel=applications")
        }

        subject = frappe.render_template(template.subject, args)
        
        # Determine the content field correctly
        message_body = ""
        if template.get("use_html"):
            message_body = frappe.render_template(template.response_html, args)
        else:
            message_body = frappe.render_template(template.response, args)

        if not message_body:
            message_body = frappe.render_template(template.get("message") or "", args)
            
        # Robust CC handling from the manual 'cc' field added to Email Template
        cc_list = []
        cc_field_value = template.get("cc")
        if cc_field_value:
            # Split by comma or semicolon, strip whitespace, and filter out empties
            cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]
        
        if message_body:
            try:
                # Use now=False to queue the email.
                frappe.sendmail(
                    recipients=[email],
                    cc=cc_list,
                    subject=subject,
                    message=message_body,
                    reference_doctype="Entrance Test Seat Allocation",
                    reference_name=doc.name,
                    now=False
                )
                frappe.logger().info(f"Entrance Test Notification Email queued successfully to {email} for {doc.name}")
            except Exception:
                frappe.log_error(traceback.format_exc(), f"Entrance Test Notification Email Queueing Failed: {doc.name}")

    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"Reschedule Email Failed: {doc.name}")


def _send_result_notification(doc, email):
    """Creates a Notification Log entry for the entrance test result."""
    if not email:
        return
    
    if frappe.db.exists("User", email):
        try:
            message_body = f"""
                <p>Your entrance test result for <strong>"{doc.entrance_test_list}"</strong> has been published.</p>
                <p>Your score: <strong>{doc.total_marks_secured_in_part_a_b}</strong></p>
                <p>Your rank: <strong>{doc.entrance_test_rank or "\u2014"}</strong></p>
                <p><a href="/merit-and-scholarship/admission_dashboard?panel=applications" style="color: #16a34a; font-weight: bold;">Click here to view details.</a></p>
            """
            
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": "Entrance Test Result Published",
                "for_user": email,
                "type": "Alert",
                "email_content": message_body,
                "document_type": "Entrance Test Seat Allocation",
                "document_name": doc.name,
                "from_user": frappe.session.user,
                "link": "/merit-and-scholarship/admission_dashboard?panel=applications"
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(message=frappe.get_traceback(), title=f"Result Notification Failed: {doc.name}")


def _send_reschedule_notification(doc, email):
    """Creates a Notification Log entry for the rescheduled entrance test."""
    if not email:
        return
    
    if frappe.db.exists("User", email):
        try:
            message_body = f"""
                <p>Your entrance test for <strong>"{doc.entrance_test_list}"</strong> has been rescheduled.</p>
                <p>Please check your admission dashboard to view the new details and select your preferred center.</p>
                <p><a href="/merit-and-scholarship/admission_dashboard?panel=applications" style="color: #16a34a; font-weight: bold;">Click here to view details.</a></p>
            """
            
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": "Entrance Test Rescheduled",
                "for_user": email,
                "type": "Alert",
                "email_content": message_body,
                "document_type": "Entrance Test Seat Allocation",
                "document_name": doc.name,
                "from_user": frappe.session.user,
                "link": "/merit-and-scholarship/admission_dashboard?panel=applications"
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(message=frappe.get_traceback(), title=f"Reschedule Notification Failed: {doc.name}")
