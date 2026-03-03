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


@frappe.whitelist()
def update_ranks_by_category(academic_year, admission_cycle, program_level, interview_list=None):
    """Rank Interview Seat Allocation records by **interview_score**.

    The caller must supply **Academic Year**, **Admission Cycle** and
    **Program Level**.  These three fields are used to filter the
    allocations; if **interview_list** is also provided the results will
    be scoped to that specific interview event as well.  Only records
    whose ``interview_status`` is ``"Attended"`` are considered.

    The method returns the number of records that were ranked.  It is
    intended to be invoked from a list-view button/dialog very similar
    to the one used by ``Entrance Test Seat Allocation``.
    """

    if not (academic_year and admission_cycle and program_level):
        frappe.throw("Academic Year, Admission Cycle, and Program Level are required for ranking.")

    # build filters
    filters = {
        "academic_year": academic_year,
        "admission_cycle": admission_cycle,
        "program_level": program_level,
        "interview_status": "Attended",
    }
    if interview_list:
        filters["interview_list"] = interview_list

    records = frappe.get_all("Interview Seat Allocation",
        filters=filters,
        fields=["name", "interview_score"],
        order_by="interview_score desc"
    )

    if not records:
        return 0

    for i, rec in enumerate(records, start=1):
        frappe.db.set_value("Interview Seat Allocation", rec.name, "rank", i, update_modified=False)

    frappe.db.commit()
    return len(records)


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
