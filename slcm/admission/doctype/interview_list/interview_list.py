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
        # Ensure schema is synced (updatedb is not a standard Frappe method)
        # frappe.db.updatedb("Interview Seat Allocation")

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
                            _send_interview_slot_email(allocation, email, staff)
                        except Exception:
                            frappe.log_error(title=f"Interview Slot Email Failed: {allocation.name}")
        
        frappe.db.commit()
        return created_count


def _send_interview_slot_email(allocation, email, staff):
    """Send a premium masterpiece interview slot assignment notification to the applicant."""
    url = get_url("/merit-and-scholarship/admission_dashboard?panel=applications")
    
    # Format Date and Time
    formatted_date = "To be communicated"
    formatted_time = "To be communicated"
    if allocation.interview_date:
        try:
            formatted_date = format_date(allocation.interview_date)
        except:
            formatted_date = str(allocation.interview_date)
            
    if allocation.interview_time:
        try:
            formatted_time = format_time(allocation.interview_time)
        except:
            formatted_time = str(allocation.interview_time)

    subject = "Admission Interview Schedule Confirmation"
    
    msg = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e1e4e8; padding: 35px; border-radius: 12px; line-height: 1.6; color: #24292e; background-color: #ffffff;">
        <p style="margin-top: 0;">Dear {allocation.candidate_name or allocation.applicant},</p>
        
        <p>Greetings from the Admissions Office.</p>
        
        <p>We are pleased to inform you that your admission interview has been successfully scheduled. The details of your interview session are provided below.</p>
        
        <div style="background-color: #f6f8fa; border-radius: 8px; padding: 20px; margin: 25px 0; border: 1px solid #e1e4e8;">
            <h4 style="margin-top: 0; margin-bottom: 12px; color: #1b1f23; font-size: 15px; border-bottom: 1px solid #d1d5da; padding-bottom: 5px;">Interview Details:</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
                <tr><td style="padding: 4px 0; color: #586069; width: 45%;">Date:</td><td style="padding: 4px 0; font-weight: 700;">{formatted_date}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Time:</td><td style="padding: 4px 0; font-weight: 700;">{formatted_time}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Venue:</td><td style="padding: 4px 0; font-weight: 700;">{allocation.interview_address or 'To be communicated'}</td></tr>
            </table>
        </div>

        <div style="background-color: #f6f8fa; border-radius: 8px; padding: 20px; margin: 25px 0; border: 1px solid #e1e4e8;">
            <h4 style="margin-top: 0; margin-bottom: 12px; color: #1b1f23; font-size: 15px; border-bottom: 1px solid #d1d5da; padding-bottom: 5px;">Applicant Information:</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
                <tr><td style="padding: 4px 0; color: #586069; width: 45%;">Application ID:</td><td style="padding: 4px 0; font-weight: 700;">{allocation.applicant}</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Program:</td><td style="padding: 4px 0; font-weight: 700;">{allocation.program} ({allocation.academic_year})</td></tr>
                <tr><td style="padding: 4px 0; color: #586069;">Campus:</td><td style="padding: 4px 0; font-weight: 700;">{allocation.campus}</td></tr>
            </table>
        </div>
        
        <p style="font-size: 12.5px; color: #6a737d; margin-bottom: 25px;">
            You are requested to report to the venue at least 15 minutes prior to the scheduled time. Please ensure that you carry all necessary documents for verification as per the admission guidelines.
        </p>

        <p>To view your complete interview details and current status, please log in to the admission portal using the link below:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{url}" style="display: inline-block; padding: 12px 28px; background-color: #0366d6; color: #ffffff; border-radius: 6px; text-decoration: none; font-weight: 700; font-size: 15px;">Interview Details</a>
        </div>
        
        <p>If you require any assistance or have queries regarding your interview schedule, please contact the Admissions Office.</p>
        
        <p>We wish you the very best for your interview.</p>
    </div>
    """

    frappe.sendmail(
        recipients=[email],
        subject=subject,
        message=msg,
        reference_doctype="Interview Seat Allocation",
        reference_name=allocation.name
    )
