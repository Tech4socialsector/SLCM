# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
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

        staff = frappe.get_doc("Interview Staff Member", staff_member)
        if not staff.is_active:
            frappe.throw(f"Staff member '{staff.staff_name}' is not active.")

        applicant_map = {row.name: row for row in self.interview_applicant}

        created_count = 0
        total_applicants = len(selected_applicants)

        for i, row_name in enumerate(selected_applicants):
            # Publish progress to the UI
            frappe.publish_progress(
                float(i + 1) / total_applicants * 100, 
                title=_("Generating Interview Slots..."),

                description=f"Processing {i + 1} of {total_applicants}"
            )

            row = applicant_map.get(row_name)
            if not row:
                continue

            if getattr(row, "interview_status", "") == "Scheduled":
                continue

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

                allocation.applicant           = row.applicant_id
                allocation.candidate_name      = row.candidate_name
                allocation.program             = row.program
                allocation.email               = row.email
                allocation.gender              = row.gender

                # FETCH CATEGORIES CORRECTLY
                if allocation.applicant:
                    try:
                        from slcm.admission.doctype.applicant.applicant import Applicant
                        app_doc = frappe.get_doc("Applicant", allocation.applicant)
                        app_categories = app_doc._get_applicant_categories()
                        allocation.set("category", [])
                        for cat in app_categories:
                            allocation.append("category", {"category": cat})
                    except Exception:
                        pass

                allocation.source_type         = row.source_type
                allocation.entrance_test_score  = row.entrance_test_score or 0

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

            row.interview_status = "Scheduled"
            created_count += 1

            # Direct SQL status update for Applicant
            if row.applicant_id:
                frappe.db.sql("""
                    UPDATE `tabApplicant` 
                    SET application_status = 'Interview Scheduled', modified = %(now)s 
                    WHERE name = %(name)s
                """, {"now": now(), "name": row.applicant_id})
                
                frappe.clear_document_cache("Applicant", row.applicant_id)
                
                frappe.publish_realtime(
                    "applicant_application_status_updated",
                    {"docname": row.applicant_id, "application_status": "Interview Scheduled"},
                )

                email = row.email or frappe.db.get_value("Applicant", row.applicant_id, "email")
                if email:
                    try:
                        _send_interview_slot_email(allocation, email)
                    except Exception:
                        frappe.log_error(message=traceback.format_exc(), title=f"Interview Slot Email Failed: {allocation.name}")
            
            # Commit periodically to update progress
            if i % 5 == 0:
                frappe.db.commit()

        self.save(ignore_permissions=True)
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
