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
    """Send interview slot assignment notification to applicant."""
    try:
        from frappe.utils import get_url_to_form
        url = get_url_to_form("Interview Seat Allocation", allocation.name)

        msg = f"""
        <p>Dear {allocation.candidate_name or allocation.applicant},</p>
        <p>Your interview has been scheduled. Please find the details below:</p>
        <p>
            <strong>Interview Details</strong><br>
            Date: {allocation.interview_date or 'To be communicated'}<br>
            Time: {allocation.interview_time or 'To be communicated'}<br>
            Interviewer: {staff.staff_name or ''}<br>
            Staff Contact: {staff.contact_number or ''}<br>
            Staff Email: {staff.email or ''}
        </p>
        <p>
            <strong>Your Details</strong><br>
            Application No: {allocation.applicant or ''}<br>
            Program: {allocation.program or ''}<br>
            Campus: {allocation.campus or ''}<br>
            Academic Year: {allocation.academic_year or ''}
        </p>
        <p>
            <a href="{url}" style="display:inline-block;padding:10px 14px;background:#1565c0;color:#fff;border-radius:4px;text-decoration:none;">
                View Interview Details
            </a>
        </p>
        <p>If the button above does not work, open: {url}</p>
        """

        frappe.sendmail(
            recipients=[email],
            subject=f"Interview Scheduled — {allocation.candidate_name or allocation.applicant}",
            message=msg,
            reference_doctype="Interview Seat Allocation",
            reference_name=allocation.name
        )
    except Exception as e:
        import traceback
        frappe.log_error(message=traceback.format_exc(), title="Send Interview Slot Email Error")
        raise
