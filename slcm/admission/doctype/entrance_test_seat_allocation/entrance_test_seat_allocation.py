import frappe
import json
import traceback
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url, get_datetime, nowdate, format_date


class EntranceTestSeatAllocation(Document):

    def validate(self):
        if self.score_obtained and self.score_obtained > 100:
            frappe.throw("Score Obtained cannot be more than 100.")

    def before_save(self):
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

def _update_applicant_status_for_entrance_test_status(applicant_name, entrance_test_status):
    """
    Update Applicant's application_status (Applicant Status doctype) when
    Entrance Test Seat Allocation's entrance_test_status is Scheduled, Rescheduled, or Absent.
    - Scheduled / Rescheduled → "Entrance Test Scheduled"
    - Absent → "Entrance Test Rejected"
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
    - Pass → "Entrance Test Completed"
    - Fail / Absent / Withheld / Disqualified → "Entrance Test Rejected"
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
    """Send a premium masterpiece result/rank notification email to the applicant."""
    url = get_url("/merit-and-scholarship/admission_dashboard?panel=applications")
    
    # Determine Status and Accents
    is_absent = (doc.entrance_test_status == "Absent")
    accent_color = "#d73a49" if is_absent else "#28a745"
    status_text = "Absent" if is_absent else (doc.result_status or doc.entrance_test_status or "Processed")
    
    # Performance Section HTML
    if is_absent:
        performance_html = f"""
        <div style="background-color: #fff5f5; border-radius: 8px; padding: 20px; margin: 25px 0; border: 1px solid #ffe3e3;">
            <p style="margin: 0; color: #d73a49; font-weight: 600; font-size: 14px;">Notice: Examination Absence</p>
            <p style="margin: 5px 0 0 0; color: #586069; font-size: 13px;">Our records indicate that you were marked as absent for this examination. As no performance data was recorded, a final score and rank have not been assigned.</p>
        </div>
        """
    else:
        score_obtained = doc.score_obtained or 0
        total_score = doc.total_score or 100
        rank = doc.entrance_test_rank or "—"
        
        performance_html = f"""
        <div style="background-color: #f6f8fa; border-radius: 8px; padding: 20px; margin: 25px 0; border: 1px solid #e1e4e8;">
            <h4 style="margin-top: 0; margin-bottom: 12px; color: #1b1f23; font-size: 15px; border-bottom: 1px solid #d1d5da; padding-bottom: 5px;">Performance Summary:</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
                <tr><td style="padding: 4px 0; color: #586069; width: 45%;">Score Obtained:</td><td style="padding: 4px 0; font-weight: 700;">{score_obtained}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Maximum Score:</td><td style="padding: 4px 0; font-weight: 700;">{total_score}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Final Rank:</td><td style="padding: 4px 0; font-weight: 700; color: #28a745; font-size: 16px;">{rank}</td></tr>
            </table>
        </div>
        """

    subject = f"Entrance Test Results – {doc.applicant}"
    
    msg = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e1e4e8; padding: 35px; border-radius: 12px; line-height: 1.6; color: #24292e; background-color: #ffffff;">
        <p style="margin-top: 0;">Dear {doc.candidate_name or doc.applicant},</p>
        
        <p>Greetings from the Admissions Office.</p>
        
        <p>We would like to inform you that the results of your Entrance Test have been officially processed. Your performance details are provided below for your reference.</p>
        
        <div style="background-color: #f6f8fa; border-radius: 8px; padding: 20px; margin: 25px 0; border: 1px solid #e1e4e8;">
            <h4 style="margin-top: 0; margin-bottom: 12px; color: #1b1f23; font-size: 15px; border-bottom: 1px solid #d1d5da; padding-bottom: 5px;">Applicant Details:</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
                <tr><td style="padding: 4px 0; color: #586069; width: 45%;">Applicant ID:</td><td style="padding: 4px 0; font-weight: 700;">{doc.applicant}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Test Name:</td><td style="padding: 4px 0; font-weight: 700;">{doc.entrance_test_name or doc.entrance_test_list}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Status:</td><td style="padding: 4px 0; font-weight: 700; color: {accent_color};">{status_text}</td></tr>
            </table>
        </div>

        {performance_html}
        
        <p>You may access your detailed result, including section-wise performance and additional information, by logging into the admission portal using the link provided below.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{url}" style="display: inline-block; padding: 12px 28px; background-color: #0366d6; color: #ffffff; border-radius: 6px; text-decoration: none; font-weight: 700; font-size: 15px;">View Result</a>
        </div>
        
        <p>Please note that further stages of the admission process, if applicable, will be communicated to you separately.</p>
        
        <p>Should you require any clarification or assistance, please feel free to contact the Admissions Office.</p>
        
        <p>We appreciate your participation and wish you the very best for the next stages of the admission process.</p>
    </div>
    """

    frappe.sendmail(
        recipients=[email],
        subject=subject,
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
    """Send a premium masterpiece reschedule notification email to the applicant."""
    url = get_url("/merit-and-scholarship/admission_dashboard?panel=applications")
    
    # Format Centers List
    centers_html = ""
    if getattr(doc, 're_assigned_preferences', None):
        for p in doc.re_assigned_preferences:
            center_display = p.center_name or p.provider
            centers_html += f'<div style="margin-bottom:4px; font-weight:600; color:#24292e;">{center_display}</div>'

    # Format Date
    formatted_date = "To be communicated"
    if doc.re_allocation_date:
        try:
            formatted_date = format_date(doc.re_allocation_date)
        except:
            formatted_date = str(doc.re_allocation_date)

    reason_html = ""
    if doc.reschedule_reason:
        reason_html = f"""
        <div style="background-color: #fffbdd; border-radius: 8px; padding: 20px; margin: 25px 0; border: 1px solid #f9eda5;">
            <p style="margin: 0; color: #735c0f; font-weight: 600; font-size: 14px;">Reason for Rescheduling:</p>
            <p style="margin: 5px 0 0 0; color: #586069; font-size: 13px;">{doc.reschedule_reason}</p>
        </div>
        """

    subject = "Entrance Test Rescheduled – Action Required"
    
    msg = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e1e4e8; padding: 35px; border-radius: 12px; line-height: 1.6; color: #24292e; background-color: #ffffff;">
        <p style="margin-top: 0;">Dear {doc.candidate_name or doc.applicant},</p>
        
        <p>Greetings from the Admissions Office.</p>
        
        <p>We are writing to inform you that your Entrance Test has been successfully rescheduled. You are now required to select your preferred test center for the new schedule.</p>
        
        <div style="background-color: #f6f8fa; border-radius: 8px; padding: 20px; margin: 25px 0; border: 1px solid #e1e4e8;">
            <h4 style="margin-top: 0; margin-bottom: 12px; color: #1b1f23; font-size: 15px; border-bottom: 1px solid #d1d5da; padding-bottom: 5px;">Rescheduled Test Details:</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
                <tr><td style="padding: 4px 0; color: #586069; width: 45%;">Applicant ID:</td><td style="padding: 4px 0; font-weight: 700;">{doc.applicant}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Test Name:</td><td style="padding: 4px 0; font-weight: 700;">{doc.re_entrance_test_name or doc.re_entrance_test_list or doc.entrance_test_list}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">New Test Date:</td><td style="padding: 4px 0; font-weight: 700;">{formatted_date}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Campus:</td><td style="padding: 4px 0; font-weight: 700;">{doc.campus}</td></tr>
            </table>
        </div>

        {reason_html}

        <div style="margin: 20px 0;">
            <h4 style="margin-top: 0; margin-bottom: 8px; color: #1b1f23; font-size: 15px;">Available Test Centers:</h4>
            <div style="padding-left: 2px;">
                {centers_html}
            </div>
        </div>
        
        <p style="font-size: 12.5px; color: #6a737d; font-style: italic; margin-bottom: 25px;">
            Kindly note that test center allocation is based on availability and will be offered on a first-come, first-served basis. Once a test center is selected, changes will not be permitted.
        </p>

        <p>You are requested to log in to the admission portal and complete your test center selection at the earliest.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{url}" style="display: inline-block; padding: 12px 28px; background-color: #0366d6; color: #ffffff; border-radius: 6px; text-decoration: none; font-weight: 700; font-size: 15px;">Select Test Center</a>
        </div>
        
        <p>Should you require any clarification or assistance, please feel free to contact the Admissions Office.</p>
        
        <p>We wish you the very best for your upcoming entrance test.</p>
    </div>
    """

    frappe.sendmail(
        recipients=[email],
        subject=subject,
        message=msg,
        reference_doctype="Entrance Test Seat Allocation",
        reference_name=doc.name
    )
