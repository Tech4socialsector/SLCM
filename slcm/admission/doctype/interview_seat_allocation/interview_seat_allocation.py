# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url, get_datetime
from datetime import datetime


class InterviewSeatAllocation(Document):
    def before_save(self):
        # mirror entrance test behaviour: stamp attendance when status changed manually
        if not self.is_new():
            old_status = frappe.db.get_value("Interview Seat Allocation", self.name, "interview_status")
            if self.interview_status != old_status:
                if self.interview_status in ["Attended", "Absent"]:
                    self.attendance_marked_on = now_datetime()

        # Fetch categories from Applicant if newly set or empty
        # Priority: Seat Allocation category (if already filled) vs Applicant's categories
        if self.applicant and (not self.category or self.is_new()):
            app_categories = frappe.get_all("Applicant Category",
                filters={"parent": self.applicant, "parenttype": "Applicant"},
                fields=["category"]
            )
            # Re-initialize the child table ONLY if it's currently empty
            if not self.category:
                for row in app_categories:
                    self.append("category", {"category": row.category})


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
    from frappe.utils import get_url_to_form
    url = get_url_to_form("Interview Seat Allocation", doc.name)

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
    <div style="font-family: sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
        <h2 style="color: #0277bd; border-bottom: 2px solid #0277bd; padding-bottom: 10px;">Interview Result</h2>
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
        
        <p style="color:#666; font-size:12px; border-top:1px solid #eee; padding-top:15px;">
            This corresponds to record: {doc.name}. If you cannot click the button, copy this link: {url}
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
        from frappe.utils import get_url_to_form
        url = get_url_to_form("Interview Seat Allocation", doc.name)

        applicant_info = f"""
        <p><strong>Applicant Details</strong><br>
        Name: {doc.candidate_name or ''}<br>
        Application No: {doc.applicant or ''}<br>
        Email: {email}
        </p>
        """

        old_info = f"""
        <p><strong>Previous Interview Details</strong><br>
        Date: {doc.interview_date or '—'}<br>
        Time: {doc.interview_time or '—'}<br>
        Staff: {doc.interview_staff_member or '—'}
        </p>
        """

        new_info = f"""
        <p><strong>New Interview Details</strong><br>
        Date: {doc.re_interview_date or '—'}<br>
        Time: {doc.re_interview_time or '—'}<br>
        Staff: {doc.re_interview_staff_member or ''}
        </p>
        """

        reason_section = ""
        if doc.reschedule_reason:
            reason_section = f"""
        <p style=\"background:#fff8e1; border-left:4px solid #ffc107; padding:10px 14px; border-radius:4px;\">
            <strong>Reason for Reschedule:</strong><br>
            {doc.reschedule_reason}
        </p>
        """

        msg = f"""
        <p>Dear {doc.candidate_name or doc.applicant},</p>
        <p>Your interview has been rescheduled.</p>
        {reason_section}
        {applicant_info}
        {old_info}
        {new_info}
        <p>
            <a href=\"{url}\" style=\"display:inline-block;padding:10px 14px;background:#1565c0;color:#fff;border-radius:4px;text-decoration:none;\">View Your Interview Details</a>
        </p>
        <p>If the button above does not work, open: {url}</p>
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
