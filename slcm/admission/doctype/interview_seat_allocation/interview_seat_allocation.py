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
    for rec in all_records:
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
                frappe.log_error(title=f"Interview Result Email Failed: {doc.name}")

    return count


def _send_result_notification_email(doc, email):
    """Send a premium masterpiece result/rank notification email to the applicant for Interview."""
    url = get_url("/merit-and-scholarship/admission_dashboard?panel=applications")
    
    # Determine Status and Accents
    is_absent = (doc.interview_status == "Absent")
    accent_color = "#d73a49" if is_absent else "#0366d6"
    
    # Resolve Result Status
    result_status = getattr(doc, "interview_result_status", None)
    status_text = "Absent" if is_absent else (result_status or doc.interview_status or "Processed")
    
    # Performance Section HTML
    if is_absent:
        performance_html = f"""
        <div style="background-color: #fff5f5; border-radius: 8px; padding: 20px; margin: 25px 0; border: 1px solid #ffe3e3;">
            <p style="margin: 0; color: #d73a49; font-weight: 600; font-size: 14px;">Notice: Interview Absence</p>
            <p style="margin: 5px 0 0 0; color: #586069; font-size: 13px;">Our records indicate that you were marked as absent for this interview session. As no evaluation was recorded, a final score and rank have not been assigned.</p>
        </div>
        """
    else:
        interview_score = doc.interview_score or 0
        rank = doc.rank or "—"
        
        performance_html = f"""
        <div style="background-color: #f6f8fa; border-radius: 8px; padding: 20px; margin: 25px 0; border: 1px solid #e1e4e8;">
            <h4 style="margin-top: 0; margin-bottom: 12px; color: #1b1f23; font-size: 15px; border-bottom: 1px solid #d1d5da; padding-bottom: 5px;">Performance Summary:</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
                <tr><td style="padding: 4px 0; color: #586069; width: 45%;">Interview Score:</td><td style="padding: 4px 0; font-weight: 700;">{interview_score}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Final Rank:</td><td style="padding: 4px 0; font-weight: 700; color: #28a745; font-size: 16px;">{rank}</td></tr>
            </table>
        </div>
        """

    subject = "Admission Interview Result Notification"
    
    msg = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e1e4e8; padding: 35px; border-radius: 12px; line-height: 1.6; color: #24292e; background-color: #ffffff;">
        <p style="margin-top: 0;">Dear {doc.candidate_name or doc.applicant},</p>
        
        <p>Greetings from the Admissions Office.</p>
        
        <p>We would like to inform you that the results of your admission interview have been officially processed. Your performance details are provided below for your reference.</p>
        
        <div style="background-color: #f6f8fa; border-radius: 8px; padding: 20px; margin: 25px 0; border: 1px solid #e1e4e8;">
            <h4 style="margin-top: 0; margin-bottom: 12px; color: #1b1f23; font-size: 15px; border-bottom: 1px solid #d1d5da; padding-bottom: 5px;">Applicant Details:</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
                <tr><td style="padding: 4px 0; color: #586069; width: 45%;">Applicant ID:</td><td style="padding: 4px 0; font-weight: 700;">{doc.applicant}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Interview Session:</td><td style="padding: 4px 0; font-weight: 700;">{doc.interview_list or '—'}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Status:</td><td style="padding: 4px 0; font-weight: 700; color: {accent_color};">{status_text}</td></tr>
            </table>
        </div>

        {performance_html}
        
        <p>You may access your detailed interview evaluation, including feedback and scoring breakdown, by logging into the admission portal using the link provided below.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{url}" style="display: inline-block; padding: 12px 28px; background-color: #0366d6; color: #ffffff; border-radius: 6px; text-decoration: none; font-weight: 700; font-size: 15px;">View Interview Result</a>
        </div>
        
        <p>Please note that further updates regarding your admission status or next steps will be communicated to you in due course.</p>
        
        <p>If you require any clarification or assistance, please feel free to contact the Admissions Office.</p>
        
        <p>We appreciate your participation in the interview process and wish you the very best.</p>
    </div>
    """

    frappe.sendmail(
        recipients=[email],
        subject=subject,
        message=msg,
        reference_doctype="Interview Seat Allocation",
        reference_name=doc.name
    )


@frappe.whitelist()
def reschedule_applicants(applicants, interview_staff=None, interview_date=None, interview_time=None, reschedule_reason=None):
    """Reschedule one or more Interview Seat Allocation records.

    * ``applicants`` should be a list of names (or JSON string).
    * ``interview_staff`` optionally selects a new interviewer.
    * ``interview_date``/``interview_time`` specify the new slot.
    * ``reschedule_reason`` is mandatory as it is emailed to candidates.
    """
    if isinstance(applicants, str):
        applicants = json.loads(applicants)

    if not applicants:
        frappe.throw("No applicants selected.")
    if not reschedule_reason:
        frappe.throw("Reason for Reschedule is mandatory.")

    # Validate interview_date is not in the past
    if interview_date and get_datetime(interview_date) < now_datetime():
        frappe.throw("New Interview Date cannot be in the past. Please select today or a future date.")

    count = 0
    for name in applicants:
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
        else:
            frappe.log_error(
                message=f"No email found for applicant {doc.applicant} (record: {doc.name}). Reschedule email was not sent.",
                title="Interview Reschedule Email Skipped"
            )

        count += 1
    frappe.db.commit()
    return count


def _send_reschedule_email(doc, email):
    """Send a premium masterpiece interview reschedule notification email to the applicant."""
    url = get_url("/merit-and-scholarship/admission_dashboard?panel=applications")
    
    # Format Date and Time
    formatted_date = "To be communicated"
    formatted_time = "To be communicated"
    if doc.re_interview_date:
        try:
            formatted_date = format_date(doc.re_interview_date)
        except:
            formatted_date = str(doc.re_interview_date)
            
    if doc.re_interview_time:
        try:
            formatted_time = format_time(doc.re_interview_time)
        except:
            formatted_time = str(doc.re_interview_time)

    reason_html = ""
    if doc.reschedule_reason:
        reason_html = f"""
        <div style="background-color: #fffbdd; border-radius: 8px; padding: 20px; margin: 25px 0; border: 1px solid #f9eda5;">
            <p style="margin: 0; color: #735c0f; font-weight: 600; font-size: 14px;">Reason for Rescheduling:</p>
            <p style="margin: 5px 0 0 0; color: #586069; font-size: 13px;">{doc.reschedule_reason}</p>
        </div>
        """

    subject = "Admission Interview Rescheduled – Action Required"
    
    msg = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e1e4e8; padding: 35px; border-radius: 12px; line-height: 1.6; color: #24292e; background-color: #ffffff;">
        <p style="margin-top: 0;">Dear {doc.candidate_name or doc.applicant},</p>
        
        <p>Greetings from the Admissions Office.</p>
        
        <p>We are writing to inform you that your admission interview has been successfully rescheduled. The details of your new interview session are provided below.</p>
        
        <div style="background-color: #f6f8fa; border-radius: 8px; padding: 20px; margin: 25px 0; border: 1px solid #e1e4e8;">
            <h4 style="margin-top: 0; margin-bottom: 12px; color: #1b1f23; font-size: 15px; border-bottom: 1px solid #d1d5da; padding-bottom: 5px;">New Interview Details:</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
                <tr><td style="padding: 4px 0; color: #586069; width: 45%;">Date:</td><td style="padding: 4px 0; font-weight: 700;">{formatted_date}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Time:</td><td style="padding: 4px 0; font-weight: 700;">{formatted_time}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Venue / Address:</td><td style="padding: 4px 0; font-weight: 700;">{doc.re_interview_address or 'To be communicated'}</td></tr>
            </table>
        </div>

        {reason_html}

        <p>Please log in to the admission portal to view your updated interview details and confirm your attendance.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{url}" style="display: inline-block; padding: 12px 28px; background-color: #0366d6; color: #ffffff; border-radius: 6px; text-decoration: none; font-weight: 700; font-size: 15px;">View Interview Details</a>
        </div>
        
        <p>If you require any assistance or have queries regarding your rescheduled interview, please contact the Admissions Office.</p>
        
        <p>We wish you the very best for your interview.</p>
    </div>
    """

    frappe.sendmail(
        recipients=[email],
        subject=subject,
        message=msg,
        reference_doctype="Interview Seat Allocation",
        reference_name=doc.name
    )
