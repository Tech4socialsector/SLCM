import frappe
import json
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url, get_datetime


class EntranceTestSeatAllocation(Document):
    def before_save(self):
        # Update attendance_marked_on if status changes to Attended, Absent, or Rescheduled
        if not self.is_new():
            old_status = frappe.db.get_value("Entrance Test Seat Allocation", self.name, "entrance_test_status")
            if self.entrance_test_status != old_status:
                if self.entrance_test_status in ["Attended", "Absent", "Rescheduled"]:
                    self.attendance_marked_on = now_datetime()

        # If score is entered, ensure status is marked as 'Attended'
        if self.score_obtained is not None and self.entrance_test_status not in ["Attended", "Absent"]:
            self.entrance_test_status = "Attended"
            self.attendance_marked_on = now_datetime()


@frappe.whitelist()
def update_ranks_by_category(academic_year, admission_cycle, program_level):
    """
    Ranks applicants based on score_obtained for a given batch.
    Filters: Academic Year, Admission Cycle, Program Level.
    Only includes those marked as 'Attended'.
    """
    if not (academic_year and admission_cycle and program_level):
        frappe.throw("Academic Year, Admission Cycle, and Program Level are required for ranking.")

    # Fetch records sorted by score_obtained descending
    records = frappe.get_all("Entrance Test Seat Allocation",
        filters={
            "academic_year": academic_year,
            "admission_cycle": admission_cycle,
            "program_level": program_level,
            "entrance_test_status": "Attended"
        },
        fields=["name", "score_obtained"],
        order_by="score_obtained desc"
    )

    if not records:
        return 0

    # Assign ranks
    for i, rec in enumerate(records, start=1):
        frappe.db.set_value("Entrance Test Seat Allocation", rec.name, "entrance_test_rank", i, update_modified=False)

    frappe.db.commit()
    return len(records)


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
    for name in applicants:
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

        # ── Resolve email ─────────────────────────────────────────────────────
        # Priority: allocation.email → Applicant doctype email
        email = doc.email or ""
        if not email and doc.applicant:
            # Try fetching from Applicant doctype
            try:
                app_email = frappe.db.get_value("Applicant", doc.applicant, "email_id")
                if app_email:
                    email = app_email
            except Exception:
                pass

        # ── Send reschedule notification email ────────────────────────────────
        if email:
            try:
                _send_reschedule_email(doc, email)
            except Exception:
                import traceback
                frappe.log_error(
                    message=traceback.format_exc(),
                    title=f"Reschedule Email Failed: {doc.name}"
                )
        else:
            frappe.log_error(
                message=f"No email found for applicant {doc.applicant} (record: {doc.name}). Reschedule email was not sent.",
                title="Reschedule Email Skipped"
            )

        count += 1

    frappe.db.commit()
    return count


    frappe.db.commit()
    return len(records)


def _send_reschedule_email(doc, email):
    """Send a reschedule notification email to the applicant."""
    try:
        url = get_url(f"/app/entrance-test-seat-allocation/{doc.name}")

        prefs_html = "<ul>"
        for p in doc.re_assigned_preferences:
            prefs_html += f"<li>{p.preference_order}. {p.center_name or p.provider} ({p.provider})</li>"
        prefs_html += "</ul>"

        applicant_info = f"""
        <p><strong>Applicant Details</strong><br>
        Name: {doc.candidate_name or ''}<br>
        Application No: {doc.applicant or ''}<br>
        Email: {email}
        </p>
        """

        past_test_info = f"""
        <p><strong>Past Test Details</strong><br>
        Entrance Test: {doc.entrance_test_list or ''}<br>
        Status: Absent
        </p>
        """

        new_test_info = f"""
        <p><strong>Rescheduled Test Details</strong><br>
        New Entrance Test Name: {doc.re_entrance_test_name or doc.re_entrance_test_list or ''}<br>
        New Allocation Date/Time: {doc.re_allocation_date or 'Not set'}<br>
        Campus: {doc.campus or ''}
        </p>
        """

        reason_section = ""
        if doc.reschedule_reason:
            reason_section = f"""
        <p style="background:#fff8e1; border-left:4px solid #ffc107; padding:10px 14px; border-radius:4px;">
            <strong>Reason for Reschedule:</strong><br>
            {doc.reschedule_reason}
        </p>
        """

        msg = f"""
        <p>Dear {doc.candidate_name or doc.applicant},</p>
        <p>You were marked as <strong>Absent</strong> for your previous entrance test. We have rescheduled the entrance test for you.</p>
        {reason_section}
        {applicant_info}
        {past_test_info}
        {new_test_info}
        <p>Please choose your preferred center from the options below for the rescheduled test:</p>
        {prefs_html}
        <p>
            <a href="{url}" style="display:inline-block;padding:10px 14px;background:#1565c0;color:#fff;border-radius:4px;text-decoration:none;">Choose Your Center for Rescheduled Test</a>
        </p>
        <p>If the button above does not work, open: {url}</p>
        """

        frappe.sendmail(
            recipients=[email],
            subject=f"Entrance Test Rescheduled — {doc.candidate_name or doc.applicant}",
            message=msg,
            reference_doctype="Entrance Test Seat Allocation",
            reference_name=doc.name
        )
    except Exception as e:
        import traceback
        frappe.log_error(message=traceback.format_exc(), title="Send Reschedule Email Error")
        raise  # Re-raise so caller can log it with doc name context
