# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
import json
import re
import traceback
from frappe.model.document import Document
from frappe.utils import now, get_url, format_date, format_time


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
                allocation.email               = row.email
                allocation.gender              = row.gender

                # Populate categories from Applicant's categories child table
                app_categories = frappe.get_all("Applicant Category",
                    filters={"parent": row.applicant_id, "parenttype": "Applicant"},
                    fields=["category"]
                )
                for cat in app_categories:
                    allocation.append("category", {"category": cat.category})

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

            # Mark child row as Scheduled
            row.interview_status = "Scheduled"
            created_count += 1

        self.save(ignore_permissions=True)
        frappe.db.commit()

        # MASTER PIECE: Absolute direct status enforcement
        for row_name in selected_applicants:
            row = applicant_map.get(row_name)
            if row and row.applicant_id:
                # Direct SQL bypasses ALL potential locks or controller logic that might revert status
                frappe.db.sql("""
                    UPDATE `tabApplicant` 
                    SET application_status = 'Interview Scheduled', modified = %(now)s 
                    WHERE name = %(name)s
                """, {"now": now(), "name": row.applicant_id})
                
                frappe.clear_document_cache("Applicant", row.applicant_id)
                
                # Notify UI with a small delay simulation via sequential calls
                frappe.publish_realtime(
                    "applicant_application_status_updated",
                    {"docname": row.applicant_id, "application_status": "Interview Scheduled"},
                )

                # Send notification email
                alloc_name = frappe.db.get_value("Interview Seat Allocation", {
                    "interview_list": self.name,
                    "applicant":      row.applicant_id
                })
                if alloc_name:
                    allocation = frappe.get_doc("Interview Seat Allocation", alloc_name)
                    email = row.email or frappe.db.get_value("Applicant", row.applicant_id, "email")
                    if email:
                        try:
                            _send_interview_slot_email(allocation, email)
                        except Exception:
                            frappe.log_error(message=traceback.format_exc(), title=f"Interview Slot Email Failed: {allocation.name}")
        
        frappe.db.commit()
        return created_count


def _send_interview_slot_email(allocation, email):
    """Send an interview slot assignment notification using a configurable template."""
    try:
        template_name = "Interview Allocation"
        if not frappe.db.exists("Email Template", template_name):
            frappe.log_error(f"Email Template '{template_name}' not found.", "Email Sending Error")
            return

        template = frappe.get_doc("Email Template", template_name)
        
        # Prepare arguments for Jinja
        doc_dict = allocation.as_dict()
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
                reference_name=allocation.name,
                now=True
            )
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"Interview Slot Email Failed: {allocation.name}")
