import frappe
import json
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url, get_datetime


class EntranceTestSeatAllocation(Document):
    def before_save(self):
        # Update attendance_marked_on if status changes to Attended, Absent, or Rescheduled
        # This only happens when the status is changed manually (Admin)
        if not self.is_new():
            old_status = frappe.db.get_value("Entrance Test Seat Allocation", self.name, "entrance_test_status")
            if self.entrance_test_status != old_status:
                if self.entrance_test_status in ["Attended", "Absent"]:
                    self.attendance_marked_on = now_datetime()


@frappe.whitelist()
def update_ranks_by_category(academic_year, admission_cycle, program_level, entrance_test_list=None):
    """
    Ranks applicants based on score_obtained for a given batch and sends result emails.
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
        fields=["name", "score_obtained"],
        order_by="score_obtained desc"
    )

    for i, rec in enumerate(attended_records, start=1):
        frappe.db.set_value("Entrance Test Seat Allocation", rec.name, "entrance_test_rank", i, update_modified=False)

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
                "score_obtained", "total_score", "entrance_test_rank", "entrance_test_list"]
    )

    count = 0
    for rec in all_records:
        doc = frappe.get_doc("Entrance Test Seat Allocation", rec.name)
        
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
                frappe.log_error(title=f"Result Email Failed: {doc.name}")

    return count


def _send_result_notification_email(doc, email):
    """Send a result/rank notification email to the applicant."""
    from frappe.utils import get_url_to_form
    url = get_url_to_form("Entrance Test Seat Allocation", doc.name)

    status_color = "#2e7d32" if doc.entrance_test_status == "Attended" else "#c62828"
    
    score_html = ""
    if doc.entrance_test_status == "Attended":
        score_html = f"""
        <div style="background:#f1f8e9; border:1px solid #c5e1a5; padding:15px; border-radius:8px; margin:20px 0;">
            <p style="margin:5px 0;"><strong>Score Obtained:</strong> {doc.score_obtained or 0} / {doc.total_score or 0}</p>
            <p style="margin:5px 0;"><strong>Final Rank:</strong> <span style="font-size:18px; color:#2e7d32; font-weight:bold;">{doc.entrance_test_rank or '—'}</span></p>
        </div>
        """
    else:
        score_html = f"""
        <div style="background:#ffebee; border:1px solid #ffcdd2; padding:15px; border-radius:8px; margin:20px 0;">
            <p style="margin:5px 0; color:#c62828;"><strong>Status:</strong> Absent</p>
            <p style="margin:5px 0; font-size:12px; color:#666;">You were marked as absent for this test. Since no score was recorded, no rank has been assigned.</p>
        </div>
        """

    msg = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
        <h2 style="color: #1565c0; border-bottom: 2px solid #1565c0; padding-bottom: 10px;">Entrance Test Result</h2>
        <p>Dear {doc.candidate_name or doc.applicant},</p>
        <p>The results for your entrance test have been processed. Below are your details:</p>
        
        <table style="width:100%; border-collapse: collapse; margin-top:10px;">
            <tr><td style="padding:8px; border-bottom:1px solid #eee;"><strong>Applicant ID:</strong></td><td style="padding:8px; border-bottom:1px solid #eee;">{doc.applicant}</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid #eee;"><strong>Test Name:</strong></td><td style="padding:8px; border-bottom:1px solid #eee;">{doc.entrance_test_list}</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid #eee;"><strong>Status:</strong></td><td style="padding:8px; border-bottom:1px solid #eee; color:{status_color}; font-weight:bold;">{doc.entrance_test_status}</td></tr>
        </table>

        {score_html}

        <p>You can view your detailed record and breakdown by clicking the button below:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{url}" style="display:inline-block; padding:12px 24px; background:#1565c0; color:#fff; border-radius:6px; text-decoration:none; font-weight:bold;">View My Result in Portal</a>
        </div>
        
        <p style="color:#666; font-size:12px; border-top:1px solid #eee; padding-top:15px;">
            This corresponds to record: {doc.name}. If you cannot click the button, copy this link: {url}
        </p>
    </div>
    """

    frappe.sendmail(
        recipients=[email],
        subject=f"Entrance Test Result — {doc.candidate_name or doc.applicant}",
        message=msg,
        reference_doctype="Entrance Test Seat Allocation",
        reference_name=doc.name
    )


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


def _send_reschedule_email(doc, email):
    """Send a reschedule notification email to the applicant."""
    try:
        from frappe.utils import get_url_to_form
        url = get_url_to_form("Entrance Test Seat Allocation", doc.name)

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
