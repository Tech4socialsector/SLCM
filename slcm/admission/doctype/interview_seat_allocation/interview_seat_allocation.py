# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url, get_datetime
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
                    self.interview_result_status != doc_before.interview_result_status):
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
        if self.interview_result_status == "Pass":
            new_status = "Interview Completed"
        elif self.interview_result_status == "Fail":
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
    """Send a result/rank notification email to the applicant for Interview."""
    from frappe.utils import get_url
    url = get_url(f"/merit-and-scholarship/admission_dashboard?panel=applications")

    status_color = "#2e7d32" if doc.interview_status == "Attended" else "#c62828"
    
    score_html = ""
    if doc.interview_status == "Attended":
        score_html = f"""
        <div style="background:#e3f2fd; border:1px solid #bbdefb; padding:15px; border-radius:8px; margin:20px 0;">
            <p style="margin:5px 0;"><strong>Interview Score:</strong> {doc.interview_score or 0}</p>
            <p style="margin:5px 0;"><strong>Final Rank:</strong> <span style="font-size:18px; color:#1565c0; font-weight:bold;">{doc.rank or '—'}</span></p>
        </div>
        """
    else:
        score_html = f"""
        <div style="background:#ffebee; border:1px solid #ffcdd2; padding:15px; border-radius:8px; margin:20px 0;">
            <p style="margin:5px 0; color:#c62828;"><strong>Status:</strong> Absent</p>
            <p style="margin:5px 0; font-size:12px; color:#666;">You were marked as absent for the interview. No score or rank has been assigned.</p>
        </div>
        """

    msg = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px; line-height: 1.6;">
        <h2 style="color: #0277bd; border-bottom: 2px solid #0277bd; padding-bottom: 10px; margin-top: 0;">Interview Result</h2>
        <p>Dear {doc.candidate_name or doc.applicant},</p>
        <p>The results for your interview have been processed. Below are your details:</p>
        
        <table style="width:100%; border-collapse: collapse; margin-top:10px;">
            <tr><td style="padding:8px; border-bottom:1px solid #eee;"><strong>Applicant ID:</strong></td><td style="padding:8px; border-bottom:1px solid #eee;">{doc.applicant}</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid #eee;"><strong>Interview Session:</strong></td><td style="padding:8px; border-bottom:1px solid #eee;">{doc.interview_list or '—'}</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid #eee;"><strong>Status:</strong></td><td style="padding:8px; border-bottom:1px solid #eee; color:{status_color}; font-weight:bold;">{doc.interview_status}</td></tr>
        </table>

        {score_html}

        <p>You can view your detailed interview feedback and score by clicking the button below:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{url}" style="display:inline-block; padding:12px 24px; background:#0277bd; color:#fff; border-radius:6px; text-decoration:none; font-weight:bold;">View My Result in Portal</a>
        </div>
        
        <p style="color:#666; font-size:12px; border-top:1px solid #eee; padding-top:15px; margin-bottom: 0;">
            Record Reference: {doc.name}. If the button doesn't work, copy this link: {url}
        </p>
    </div>
    """

    frappe.sendmail(
        recipients=[email],
        subject=f"Interview Result — {doc.candidate_name or doc.applicant}",
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
                import traceback
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
    """Email notification for interview reschedule."""
    try:
        from frappe.utils import get_url
        url = get_url(f"/merit-and-scholarship/admission_dashboard?panel=applications")

        reason_section = ""
        if doc.reschedule_reason:
            reason_section = f"""
            <div style="background: #fff8e1; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px;">
                <p style="margin: 0;"><strong>Reason for Reschedule:</strong><br>{doc.reschedule_reason}</p>
            </div>
            """

        msg = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px; line-height: 1.6; color: #333;">
            <h2 style="color: #0277bd; border-bottom: 2px solid #0277bd; padding-bottom: 10px; margin-top: 0;">Admission Interview Rescheduled</h2>
            <p>Dear {doc.candidate_name or doc.applicant},</p>
            <p>Your admission interview has been rescheduled. Please find the new session details below:</p>
            
            {reason_section}

            <div style="background: #e3f2fd; border-radius: 8px; padding: 15px; margin: 20px 0;">
                <p style="margin: 0 0 10px 0;"><strong>New Interview Details:</strong></p>
                <table style="width:100%; border-collapse: collapse; font-size: 14px;">
                    <tr><td style="padding:5px 0; color:#666;">Date:</td><td style="padding:5px 0; font-weight:bold;">{doc.re_interview_date or 'To be communicated'}</td></tr>
                    <tr><td style="padding:5px 0; color:#666;">Time:</td><td style="padding:5px 0; font-weight:bold;">{doc.re_interview_time or 'To be communicated'}</td></tr>
                    <tr><td style="padding:5px 0; color:#666;">Venue / Address:</td><td style="padding:5px 0; font-weight:bold;">{doc.re_interview_address or 'To be communicated'}</td></tr>
                </table>
            </div>

            <p>Please click the button below to view your updated interview details in the portal:</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{url}" style="display:inline-block; padding:12px 28px; background:#0277bd; color:#fff; border-radius:6px; text-decoration:none; font-weight:bold; font-size: 16px;">View Interview Details</a>
            </div>
            
            <p style="color:#666; font-size:12px; border-top:1px solid #eee; padding-top:15px; margin-bottom: 0;">
                Record Reference: {doc.name}<br>
                If the button doesn't work, copy this link: {url}
            </p>
        </div>
        """

        frappe.sendmail(
            recipients=[email],
            subject=f"Interview Rescheduled — {doc.candidate_name or doc.applicant}",
            message=msg,
            reference_doctype="Interview Seat Allocation",
            reference_name=doc.name
        )
    except Exception:
        import traceback
        frappe.log_error(message=traceback.format_exc(), title="Interview Reschedule Email Error")
        raise
