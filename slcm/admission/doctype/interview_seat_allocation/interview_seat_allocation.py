# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
import json
import traceback
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url, get_datetime, format_date, format_time
from datetime import datetime


class InterviewSeatAllocation(Document):
    def validate(self):
        if self.interview_score and self.interview_score > 100:
            frappe.throw("Interview Score cannot be more than 100.")

    def before_save(self):
        doc_before = self.get_doc_before_save()
        # Mirror entrance test behaviour: stamp attendance when status changed manually
        if not self.is_new():
            if doc_before and self.interview_status != doc_before.interview_status:
                if self.interview_status in ["Attended", "Absent"]:
                    self.attendance_marked_on = now_datetime()

        # Update Applicant's application_status when relevant fields change
        if self.applicant:
            status_changed = False
            if self.is_new():
                status_changed = True
            elif doc_before:
                if (self.interview_status != doc_before.interview_status or 
                    getattr(self, "interview_result_status", None) != getattr(doc_before, "interview_result_status", None)):
                    status_changed = True
            
            if status_changed:
                self._sync_applicant_status()

        # FETCH CATEGORIES CORRECTLY
        if self.applicant and (not self.category or self.is_new()):
            try:
                from slcm.admission.doctype.applicant.applicant import Applicant
                app_doc = frappe.get_doc("Applicant", self.applicant)
                app_categories = app_doc._get_applicant_categories()
                # Re-initialize the child table ONLY if it's currently empty
                if not self.category:
                    self.set("category", [])
                    for cat in app_categories:
                        self.append("category", {"category": cat})
            except Exception:
                pass

    def _sync_applicant_status(self):
        """
        Determine and set the Applicant's application_status based on Interview and Result statuses.
        - Result Pass → "Interview Completed"
        - Result Fail → "Interview Rejected"
        - Status Absent → "Interview Rejected"
        - Status Scheduled → "Interview Scheduled"
        """
        new_status = None
        
        # 1. Result Status takes precedence
        result_status = getattr(self, "interview_result_status", None)
        if result_status == "Pass":
            new_status = "Interview Completed"
        elif result_status == "Fail":
            new_status = "Interview Rejected"
        
        # 2. Then Interview Status (only if no result status)
        if not new_status:
            if self.interview_status == "Absent":
                new_status = "Interview Rejected"
            elif self.interview_status == "Scheduled":
                new_status = "Interview Scheduled"
        
        if not new_status:
            return

        # Use helper to perform update
        _update_applicant_status(self.applicant, new_status)


def _update_applicant_status(applicant_name, new_status):
    """Update Applicant's application_status and notify clients."""
    if not frappe.db.exists("Applicant Status", new_status):
        frappe.log_error(
            message=f"Applicant Status '{new_status}' does not exist. Create it in Applicant Status doctype.",
            title="Applicant Status Sync Skipped (Interview)",
        )
        return

    frappe.db.set_value("Applicant", applicant_name, "application_status", new_status)
    frappe.db.commit()
    frappe.clear_document_cache("Applicant", applicant_name)
    
    # Notify clients
    frappe.publish_realtime(
        "applicant_application_status_updated",
        {"docname": applicant_name, "application_status": new_status},
    )


def _update_applicant_status_for_interview_status(applicant_name, interview_status):
    """Backward compatibility helper (deprecated but kept if called elsewhere)."""
    status_map = {
        "Scheduled": "Interview Scheduled",
        "Absent": "Interview Rejected",
    }
    new_status = status_map.get(interview_status)
    if new_status:
        _update_applicant_status(applicant_name, new_status)

def _update_applicant_status_for_interview_result_status(applicant_name, interview_result_status):
    """Backward compatibility helper (deprecated but kept if called elsewhere)."""
    if interview_result_status == "Pass":
        _update_applicant_status(applicant_name, "Interview Completed")
    elif interview_result_status == "Fail":
        _update_applicant_status(applicant_name, "Interview Rejected")


@frappe.whitelist()
def update_ranks_by_category(academic_year, admission_cycle, program_level, interview_list=None):
    """
    Rank Interview Seat Allocation records by **interview_score** and send results.
    """
    if not (academic_year and admission_cycle and program_level):
        frappe.throw("Academic Year, Admission Cycle, and Program Level are required for ranking.")

    # 1. Rank Attended applicants
    attended_filters = {
        "academic_year": academic_year,
        "admission_cycle": admission_cycle,
        "program_level": program_level,
        "interview_status": "Attended",
    }
    if interview_list:
        attended_filters["interview_list"] = interview_list

    attended_records = frappe.get_all("Interview Seat Allocation",
        filters=attended_filters,
        fields=["name", "interview_score"],
        order_by="interview_score desc"
    )

    for i, rec in enumerate(attended_records, start=1):
        frappe.db.set_value("Interview Seat Allocation", rec.name, {
            "rank": i,
            "result_published": 1
        }, update_modified=False)

    frappe.db.commit()

    # 2. Fetch ALL applicants (Attended + Absent) to send notifications and mark published
    all_filters = {
        "academic_year": academic_year,
        "admission_cycle": admission_cycle,
        "program_level": program_level,
        "interview_status": ["in", ["Attended", "Absent"]]
    }
    if interview_list:
        all_filters["interview_list"] = interview_list

    all_records = frappe.get_all("Interview Seat Allocation",
        filters=all_filters,
        fields=["name", "applicant", "candidate_name", "email", "interview_status", 
                "interview_score", "rank", "interview_list"]
    )

    count = 0
    total = len(all_records)
    for i, rec in enumerate(all_records):
        # Publish progress
        frappe.publish_progress(
            float(i + 1) / total * 100, 
            title="Sending Interview Results...", 
            description=f"Notifying {i + 1} of {total}"
        )

        doc = frappe.get_doc("Interview Seat Allocation", rec.name)
        
        # Set result_published for all notified candidates
        if not doc.result_published:
            doc.db_set("result_published", 1)
        
        # Resolve email
        email = doc.email or ""
        if not email and doc.applicant:
            try:
                app_email = frappe.db.get_value("Applicant", doc.applicant, "email_id")
                if app_email:
                    email = app_email
            except Exception:
                pass

        if email:
            try:
                _send_result_notification_email(doc, email)
                count += 1
            except Exception:
                frappe.log_error(message=traceback.format_exc(), title=f"Interview Result Email Failed: {doc.name}")
        
        if i % 5 == 0:
            frappe.db.commit()

    return count


def _send_result_notification_email(doc, email):
    """Send a result/rank notification email using a configurable template for Interview."""
    try:
        template_name = "Interview Result"
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
        message_body = template.response_html if template.use_html else template.response
        
        if message_body:
            message = frappe.render_template(message_body, args)
            frappe.sendmail(
                recipients=[email],
                subject=subject,
                content=message,
                reference_doctype="Interview Seat Allocation",
                reference_name=doc.name,
                now=True
            )
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"Interview Result Email Failed: {doc.name}")


@frappe.whitelist()
def reschedule_applicants(applicants, interview_staff=None, interview_date=None, interview_time=None, reschedule_reason=None):
    """Reschedule one or more Interview Seat Allocation records.
    """
    if isinstance(applicants, str):
        applicants = json.loads(applicants)

    if not applicants:
        frappe.throw("No applicants selected.")
    if not reschedule_reason:
        frappe.throw("Reason for Reschedule is mandatory.")

    # Validate interview_date is not in the past
    if allocation_date := interview_date:
        if get_datetime(allocation_date) < now_datetime():
            frappe.throw("New Interview Date cannot be in the past. Please select today or a future date.")

    count = 0
    total = len(applicants)
    for i, name in enumerate(applicants):
        # Publish progress
        frappe.publish_progress(
            float(i + 1) / total * 100, 
            title="Rescheduling Interviews...", 
            description=f"Processing {i + 1} of {total}"
        )

        doc = frappe.get_doc("Interview Seat Allocation", name)

        doc.is_rescheduled = 1
        doc.re_interview_staff_member = interview_staff
        # Normalize incoming interview_date (may be a datetime string) to Date
        dt = None
        if interview_date:
            try:
                dt = get_datetime(interview_date)
                # store only date part (DocType field is Date)
                doc.re_interview_date = dt.date().isoformat()
            except Exception:
                # fallback: save raw value
                doc.re_interview_date = interview_date

        # Normalize interview_time into HH:MM:SS (24-hour) for MySQL TIME column
        normalized_time = None
        if interview_time:
            t = interview_time.strip()
            # Try several common formats
            for fmt in ("%I:%M %p", "%I:%M:%S %p", "%H:%M:%S", "%H:%M"):
                try:
                    parsed = datetime.strptime(t, fmt)
                    normalized_time = parsed.strftime("%H:%M:%S")
                    break
                except Exception:
                    continue
            # if still not parsed and we have a datetime from interview_date, take its time
            if not normalized_time and dt:
                try:
                    normalized_time = dt.time().strftime("%H:%M:%S")
                except Exception:
                    normalized_time = None
        else:
            # If no explicit time provided, try deriving from interview_date
            if dt:
                try:
                    normalized_time = dt.time().strftime("%H:%M:%S")
                except Exception:
                    normalized_time = None

        # Assign normalized time (or raw value as fallback)
        if normalized_time:
            doc.re_interview_time = normalized_time
        else:
            doc.re_interview_time = interview_time
        doc.re_interview_slot_status = "Slot Assigned"
        doc.reschedule_reason = reschedule_reason
        # reset status back to scheduled so that attendance can be marked later
        doc.interview_status = "Scheduled"

        doc.save(ignore_permissions=True)

        # resolve email
        email = doc.email or ""
        if not email and doc.applicant:
            try:
                app_email = frappe.db.get_value("Applicant", doc.applicant, "email_id")
                if app_email:
                    email = app_email
            except Exception:
                pass

        if email:
            try:
                _send_reschedule_email(doc, email)
            except Exception:
                frappe.log_error(
                    message=traceback.format_exc(),
                    title=f"Interview Reschedule Email Failed: {doc.name}"
                )
        
        if i % 5 == 0:
            frappe.db.commit()

        count += 1
    frappe.db.commit()
    return count


def _send_reschedule_email(doc, email):
    """Send an interview reschedule notification email using a configurable template."""
    try:
        template_name = "Interview Reschedule"
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
        message_body = template.response_html if template.use_html else template.response
        
        if message_body:
            message = frappe.render_template(message_body, args)
            frappe.sendmail(
                recipients=[email],
                subject=subject,
                content=message,
                reference_doctype="Interview Seat Allocation",
                reference_name=doc.name,
                now=True
            )
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"Interview Reschedule Email Failed: {doc.name}")
