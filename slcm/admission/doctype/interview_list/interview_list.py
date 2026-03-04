# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
import json
import re
from frappe.model.document import Document


class InterviewList(Document):

    def autoname(self):
        """
        Custom naming: IVL-{academic_year}-###
        Gap-filling strategy — reuses deleted numbers.
        """
        if self.academic_year:
            prefix = f"IVL-{self.academic_year}-"

            rows = frappe.db.sql(
                "SELECT name FROM `tabInterview List` WHERE name LIKE %s",
                prefix + "%",
                as_list=True,
            )

            used = set()
            pattern = re.compile(re.escape(prefix) + r"(\d{1,})$")
            for r in rows:
                m = pattern.match(r[0])
                if m:
                    try:
                        used.add(int(m.group(1)))
                    except ValueError:
                        pass

            idx = 1
            while idx in used:
                idx += 1

            self.name = f"{prefix}{idx:03d}"
        else:
            self.name = frappe.generate_hash(self.doctype, 6)

    @frappe.whitelist()
    def allocate_interview_slots(self, staff_member, selected_applicants, interview_date=None, interview_time=None):
        """
        Admin selects:
          - staff_member         : one Interview Staff Member name
          - selected_applicants  : list of child-table row names (interview_applicant)
          - interview_date       : optional date for the interview
          - interview_time       : optional time slot

        Logic:
          - Creates ONE Interview Seat Allocation record per selected applicant.
          - Assigns the chosen staff member.
          - Marks child row as 'Scheduled'.
          - Sends email notification to each applicant.
        """
        # Ensure schema is synced
        frappe.db.updatedb("Interview Seat Allocation")

        if isinstance(selected_applicants, str):
            selected_applicants = json.loads(selected_applicants)

        if not staff_member:
            frappe.throw("Please select an Interview Staff Member.")
        if not selected_applicants:
            frappe.throw("No applicants selected.")

        # Validate staff member is active
        staff = frappe.get_doc("Interview Staff Member", staff_member)
        if not staff.is_active:
            frappe.throw(f"Staff member '{staff.staff_name}' is not active.")

        # Build lookup map for child rows
        applicant_map = {row.name: row for row in self.interview_applicant}

        created_count = 0

        for row_name in selected_applicants:
            row = applicant_map.get(row_name)
            if not row:
                continue

            # Skip already scheduled
            if getattr(row, "interview_status", "") == "Scheduled":
                continue

            # Check if allocation already exists for this applicant in this list
            existing = frappe.db.get_value("Interview Seat Allocation", {
                "interview_list": self.name,
                "applicant":      row.applicant_id
            }, "name")

            if existing:
                allocation = frappe.get_doc("Interview Seat Allocation", existing)
            else:
                allocation = frappe.new_doc("Interview Seat Allocation")
                allocation.interview_list      = self.name
                allocation.academic_year       = self.academic_year
                allocation.admission_cycle     = self.admission_cycle
                allocation.campus              = self.campus
                allocation.program_level       = self.program_level

                # Applicant details
                allocation.applicant           = row.applicant_id
                allocation.candidate_name      = row.candidate_name
                allocation.program             = row.program
                allocation.reservation_category = row.reservation_category
                allocation.email               = row.email
                allocation.gender              = row.gender

                # Source tracking
                allocation.source_type         = row.source_type
                allocation.entrance_test_score  = row.entrance_test_score or 0

            # Assign staff member
            allocation.interview_staff_member = staff_member
            allocation.staff_name             = staff.staff_name
            allocation.staff_email            = staff.email
            allocation.staff_contact          = staff.contact_number
            allocation.interview_slot_status  = "Slot Assigned"
            allocation.slot_assigned_by       = frappe.session.user
            allocation.interview_status       = "Scheduled"

            if interview_date:
                allocation.interview_date = interview_date
            if interview_time:
                allocation.interview_time = interview_time

            allocation.save(ignore_permissions=True)

            # Send notification email
            email = row.email or ""
            if not email and row.applicant_id:
                try:
                    email = frappe.db.get_value("Applicant", row.applicant_id, "email") or ""
                except Exception:
                    pass

            if email:
                try:
                    _send_interview_slot_email(allocation, email, staff)
                except Exception:
                    import traceback
                    frappe.log_error(
                        message=traceback.format_exc(),
                        title=f"Interview Slot Email Failed: {allocation.name}"
                    )

            # Mark child row as Scheduled
            row.interview_status = "Scheduled"
            created_count += 1

        self.save(ignore_permissions=True)
        frappe.db.commit()

        return created_count


def _send_interview_slot_email(allocation, email, staff):
    """Send a premium interview slot assignment notification to the applicant."""
    from frappe.utils import get_url_to_form
    url = get_url_to_form("Interview Seat Allocation", allocation.name)

    msg = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px; line-height: 1.6; color: #333;">
        <h2 style="color: #0277bd; border-bottom: 2px solid #0277bd; padding-bottom: 10px; margin-top: 0;">Admission Interview Scheduled</h2>
        <p>Dear {allocation.candidate_name or allocation.applicant},</p>
        <p>Your admission interview has been scheduled. Please find the session details below:</p>
        
        <div style="background: #e3f2fd; border-radius: 8px; padding: 15px; margin: 20px 0;">
            <p style="margin: 0 0 10px 0;"><strong>Interview Details:</strong></p>
            <table style="width:100%; border-collapse: collapse; font-size: 14px;">
                <tr><td style="padding:5px 0; color:#666;">Date:</td><td style="padding:5px 0; font-weight:bold;">{allocation.interview_date or 'To be communicated'}</td></tr>
                <tr><td style="padding:5px 0; color:#666;">Time:</td><td style="padding:5px 0; font-weight:bold;">{allocation.interview_time or 'To be communicated'}</td></tr>
                <tr><td style="padding:5px 0; color:#666;">Interviewer:</td><td style="padding:5px 0; font-weight:bold;">{staff.staff_name or ''}</td></tr>
                <tr><td style="padding:5px 0; color:#666;">Staff Contact:</td><td style="padding:5px 0; font-weight:bold;">{staff.contact_number or ''}</td></tr>
            </table>
        </div>

        <div style="background: #f8f9fa; border-radius: 8px; padding: 15px; margin: 20px 0; font-size: 13px;">
            <p style="margin: 0 0 5px 0; color:#666;"><strong>Your Information:</strong></p>
            <p style="margin: 0;">ID: {allocation.applicant} | {allocation.program} ({allocation.academic_year})</p>
            <p style="margin: 0;">Campus: {allocation.campus}</p>
        </div>

        <p>Please click the button below to view your full interview details and status in the portal:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{url}" style="display:inline-block; padding:12px 28px; background:#0277bd; color:#fff; border-radius:6px; text-decoration:none; font-weight:bold; font-size: 16px;">View Interview Details</a>
        </div>
        
        <p style="color:#666; font-size:12px; border-top:1px solid #eee; padding-top:15px; margin-bottom: 0;">
            Record Reference: {allocation.name}<br>
            If the button doesn't work, copy this link: {url}
        </p>
    </div>
    """

    frappe.sendmail(
        recipients=[email],
        subject=f"Interview Scheduled — {allocation.candidate_name or allocation.applicant}",
        message=msg,
        reference_doctype="Interview Seat Allocation",
        reference_name=allocation.name
    )
