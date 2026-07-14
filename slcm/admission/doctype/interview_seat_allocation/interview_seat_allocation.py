# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
import traceback
from frappe.model.document import Document
from frappe.utils import now_datetime, get_url, get_datetime, format_date, format_time, flt
from datetime import datetime


class InterviewSeatAllocation(Document):
    def validate(self):
        if self.interview_score and self.interview_score > 30:
            frappe.throw("Interview Score cannot be more than 30.")
        self._fetch_entrance_test_details()
        self.calculate_final_cumulative()

    def calculate_final_cumulative(self):
        """
        Auto-calculate only the numeric score fields.
        Result Status (interview_result_status) and Offered Admission (offered_admission)
        are purely manual — never auto-set or overwritten by the system.
        """
        et_marks = flt(self.et_total_marks_secured_in_part_a_b or 0)
        et_max = flt(self.et_total_marks or 0)
        interview_max = 30.0
        score = flt(self.interview_score or 0)
        max_marks = et_max + interview_max

        if self.interview_status == "Attended":
            self.final_cumulative_score = et_marks + score
            self.final_percentage = (
                self.final_cumulative_score / max_marks * 100.0
            ) if max_marks > 0 else 0.0
        elif self.interview_status == "Absent":
            self.final_cumulative_score = 0.0
            self.final_percentage = 0.0
        else:
            self.final_cumulative_score = 0.0
            self.final_percentage = 0.0


    def before_save(self):
        doc_before = self.get_doc_before_save()
        # Mirror entrance test behaviour: stamp attendance when status changed manually
        if not self.is_new():
            if doc_before and self.interview_status != doc_before.interview_status:
                if self.interview_status in ["Attended", "Absent"]:
                    self.attendance_marked_on = now_datetime()

        # Update Applicant's status when relevant fields change
        if self.applicant:
            status_changed = False
            if self.is_new():
                status_changed = True
            elif doc_before:
                if (self.interview_status != doc_before.interview_status or 
                    getattr(self, "interview_result_status", None) != getattr(doc_before, "interview_result_status", None)):
                    status_changed = True
            
            if status_changed:
                self._sync_applicant_status()

        # FETCH CATEGORIES CORRECTLY
        if self.applicant and (not self.category or self.is_new()):
            try:
                from slcm.admission.doctype.applicant.applicant import Applicant
                app_doc = frappe.get_doc("Applicant", self.applicant)
                app_categories = app_doc._get_applicant_categories()
                # Re-initialize the child table ONLY if it's currently empty
                if not self.category:
                    self.set("category", [])
                    for cat in app_categories:
                        self.append("category", {"category": cat})
            except Exception:
                pass

        # FETCH ENTRANCE TEST DETAILS
        self._fetch_entrance_test_details()

    def _fetch_entrance_test_details(self):
        """Fetch entrance test result details from Entrance Test Seat Allocation."""
        if not self.applicant:
            return

        etsa = frappe.db.get_value("Entrance Test Seat Allocation", {"applicant": self.applicant}, [
            "attendance_marked_on", "total_marks", "part_a_total_marks_scored",
            "part_a_all_india_rank", "part_b_total_marks_scored", "part_b_all_india_rank",
            "total_marks_secured_in_part_a_b", "percentage", "entrance_test_rank",
            "percentile", "result_status", "result_published"
        ], as_dict=True)

        if etsa:
            self.et_attendance_marked_on = etsa.attendance_marked_on
            self.et_total_marks = etsa.total_marks
            self.et_part_a_total_marks_scored = etsa.part_a_total_marks_scored
            self.et_part_a_all_india_rank = etsa.part_a_all_india_rank
            self.et_part_b_total_marks_scored = etsa.part_b_total_marks_scored
            self.et_part_b_all_india_rank = etsa.part_b_all_india_rank
            self.et_total_marks_secured_in_part_a_b = etsa.total_marks_secured_in_part_a_b
            self.et_percentage = etsa.percentage
            self.et_entrance_test_rank = etsa.entrance_test_rank
            self.et_percentile = etsa.percentile
            self.et_result_status = etsa.result_status
            self.et_result_published = etsa.result_published
            self.et_source = "Entrance Test"
        else:
            # Handle exempted or other sources
            if getattr(self, "source_type", None) != "Entrance Test":
                self.et_total_marks = 0
                self.et_part_a_total_marks_scored = 0
                self.et_part_a_all_india_rank = 0
                self.et_part_b_total_marks_scored = 0
                self.et_part_b_all_india_rank = 0
                self.et_total_marks_secured_in_part_a_b = 0
                self.et_percentage = 0
                self.et_entrance_test_rank = 0
                self.et_percentile = 0
                self.et_source = getattr(self, "source_type", "Exempted")

    def _sync_applicant_status(self):
        """
        Determine and set the Applicant's status based on Interview and Result statuses.
        - Result Pass → "Interview Completed"
        - Result Fail → "Interview Rejected"
        - Status Absent → "Interview Rejected"
        - Status Scheduled → "Interview Scheduled"
        """
        new_status = None
        
        # 1. Result Status takes precedence
        result_status = getattr(self, "interview_result_status", None)
        if result_status == "Pass":
            new_status = "Interview Completed"
        elif result_status == "Fail":
            new_status = "Interview Rejected"
        
        # 2. Then Interview Status (only if no result status)
        if not new_status:
            if self.interview_status == "Absent":
                new_status = "Interview Rejected"
            elif self.interview_status == "Scheduled":
                new_status = "Interview Scheduled"
        
        if not new_status:
            return

        # Use helper to perform update
        _update_applicant_status(self.applicant, new_status)


def _update_applicant_status(applicant_name, new_status):
    """Update Applicant's status and notify clients."""
    if not frappe.db.exists("Applicant Status", new_status):
        frappe.log_error(
            message=f"Applicant Status '{new_status}' does not exist. Create it in Applicant Status doctype.",
            title="Applicant Status Sync Skipped (Interview)",
        )
        return

    frappe.db.set_value("Applicant", applicant_name, "status", new_status)
    frappe.db.commit()
    frappe.clear_document_cache("Applicant", applicant_name)
    
    # Notify clients
    frappe.publish_realtime(
        "applicant_status_updated",
        {"docname": applicant_name, "status": new_status},
    )


def _update_applicant_status_for_interview_status(applicant_name, interview_status):
    """Backward compatibility helper (deprecated but kept if called elsewhere)."""
    status_map = {
        "Scheduled": "Interview Scheduled",
        "Absent": "Interview Rejected",
    }
    new_status = status_map.get(interview_status)
    if new_status:
        _update_applicant_status(applicant_name, new_status)

def _update_applicant_status_for_interview_result_status(applicant_name, interview_result_status):
    """Backward compatibility helper (deprecated but kept if called elsewhere)."""
    if interview_result_status == "Pass":
        _update_applicant_status(applicant_name, "Interview Completed")
    elif interview_result_status == "Fail":
        _update_applicant_status(applicant_name, "Interview Rejected")


@frappe.whitelist()
def update_ranks_by_category(academic_year, admission_cycle, program_level, interview_list=None):
    """
    Recalculates cumulative marks, offered admission status, assigns ranks to Attended applicants,
    publishes results, and sends notification emails.
    """
    if not (academic_year and admission_cycle and program_level):
        frappe.throw("Academic Year, Admission Cycle, and Programme Level are required.")

    # Fetch ALL applicants (Attended + Absent) to process
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
        fields=["name", "interview_status"]
    )

    # 1. Update cumulative scores and publish result
    for rec in all_records:
        doc = frappe.get_doc("Interview Seat Allocation", rec.name)
        doc.result_published = 1
        # Calling save will trigger validate -> calculate_final_cumulative
        doc.save(ignore_permissions=True)

    frappe.db.commit()

    # 2. Rank Attended applicants based on final_cumulative_score desc
    attended_filters = {
        "academic_year": academic_year,
        "admission_cycle": admission_cycle,
        "program_level": program_level,
        "interview_status": "Attended"
    }
    if interview_list:
        attended_filters["interview_list"] = interview_list

    attended_records = frappe.get_all("Interview Seat Allocation",
        filters=attended_filters,
        fields=["name", "final_cumulative_score"],
        order_by="final_cumulative_score desc"
    )

    total_attended = len(attended_records)
    if total_attended > 0:
        # Rank competitive sorting (ties get same rank)
        sorted_recs = sorted(attended_records, key=lambda x: flt(x.get("final_cumulative_score")), reverse=True)
        last_score = None
        current_rank = 0
        for idx, rec in enumerate(sorted_recs, start=1):
            score = flt(rec.get("final_cumulative_score"))
            if last_score is None or score != last_score:
                current_rank = idx
                last_score = score
            
            frappe.db.set_value("Interview Seat Allocation", rec.name, "rank", current_rank, update_modified=False)
        
        frappe.db.commit()

    # Clear ranks for Absent/non-Attended
    absent_filters = all_filters.copy()
    absent_filters["interview_status"] = ["!=", "Attended"]
    absent_records = frappe.get_all("Interview Seat Allocation", filters=absent_filters, fields=["name"])
    for rec in absent_records:
        frappe.db.set_value("Interview Seat Allocation", rec.name, "rank", 0, update_modified=False)
    
    frappe.db.commit()

    # 3. Send email notifications and notification logs
    count = 0
    total = len(all_records)
    for i, rec in enumerate(all_records):
        # Publish progress
        percent = (float(i + 1) / total) * 100
        frappe.publish_progress(
            percent, 
            title=_("Updating Ranks & Sending Emails..."), 
            description=f"Processing {i + 1} of {total}"
        )

        # Reload doc to get updated rank
        doc = frappe.get_doc("Interview Seat Allocation", rec.name)
        
        # Resolve email
        email = doc.email or ""
        if not email and doc.applicant:
            try:
                app_email = frappe.db.get_value("Applicant", doc.applicant, "email")
                if app_email:
                    email = app_email
            except Exception:
                pass

        if email:
            try:
                _send_result_notification_email(doc, email)
                _send_result_notification(doc, email)
                count += 1
            except Exception:
                frappe.log_error(message=traceback.format_exc(), title=f"Interview Result Email/Notification Failed: {doc.name}")
        
        if i % 10 == 0:
            frappe.db.commit()

    frappe.db.commit()
    return count



def _send_result_notification_email(doc, email):
    """Send a result/rank notification email using a configurable template for Interview."""
    try:
        template_name = "Interview Result"
        if not frappe.db.exists("Email Template", template_name):
            frappe.log_error(f"Email Template '{template_name}' not found.", "Email Sending Error")
            return

        template = frappe.get_doc("Email Template", template_name)
        
        # Prepare arguments for Jinja
        doc_dict = doc.as_dict()
        args = {
            "doc": doc_dict,
            "portal_url": get_url("/merit-and-scholarship/admission_dashboard?panel=applications")
        }

        subject = frappe.render_template(template.subject, args)
        
        # Determine the content field correctly
        message_body = ""
        if template.get("use_html"):
            message_body = frappe.render_template(template.response_html, args)
        else:
            message_body = frappe.render_template(template.response, args)

        if not message_body:
            message_body = frappe.render_template(template.get("message") or "", args)
            
        # Robust CC handling from the manual 'cc' field added to Email Template
        cc_list = []
        cc_field_value = template.get("cc")
        if cc_field_value:
            # Split by comma or semicolon, strip whitespace, and filter out empties
            cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]
        
        if message_body:
            try:
                # Use now=False to queue the email.
                sender = None
                if template.get("email_account"):
                    sender = frappe.db.get_value("Email Account", template.get("email_account"), "email_id") or template.get("email_account")

                frappe.sendmail(
                    recipients=[email],
                    sender=sender,
                    cc=cc_list,
                    subject=subject,
                    message=message_body,
                    reference_doctype="Interview Seat Allocation",
                    reference_name=doc.name,
                    now=False
                )
                frappe.logger().info(f"Interview Notification Email queued successfully to {email} for {doc.name}")
            except Exception:
                frappe.log_error(traceback.format_exc(), f"Interview Notification Email Queueing Failed: {doc.name}")
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"Interview Result Email Failed: {doc.name}")


@frappe.whitelist()
def reschedule_applicants(applicants, interview_staff=None, interview_date=None, interview_time=None, reschedule_reason=None):
    """Reschedule one or more Interview Seat Allocation records.
    """
    if isinstance(applicants, str):
        applicants = json.loads(applicants)

    if not applicants:
        frappe.throw("No applicants selected.")
    if not reschedule_reason:
        frappe.throw("Reason for Reschedule is mandatory.")

    # Validate interview_date is not in the past
    if allocation_date := interview_date:
        if get_datetime(allocation_date) < now_datetime():
            frappe.throw("New Interview Date cannot be in the past. Please select today or a future date.")

    count = 0
    total = len(applicants)
    for i, name in enumerate(applicants):
        # Publish progress
        percent = (float(i + 1) / total * 100)
        frappe.publish_progress(
            percent, 
            title=_("Rescheduling Interviews..."), 
            description=f"Processing {i + 1} of {total}"
        )

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
                app_email = frappe.db.get_value("Applicant", doc.applicant, "email")
                if app_email:
                    email = app_email
            except Exception:
                pass

        if email:
            try:
                _send_reschedule_email(doc, email)
                _send_reschedule_notification(doc, email)
            except Exception:
                frappe.log_error(
                    message=traceback.format_exc(),
                    title=f"Interview Reschedule Email/Notification Failed: {doc.name}"
                )
        
        if i % 5 == 0:
            frappe.db.commit()

        count += 1

    # Send combined email to the interviewer for rescheduling
    if count > 0 and interview_staff:
        try:
            _send_interviewer_reschedule_email(interview_staff, interview_date, interview_time, reschedule_reason, applicants)
            _send_interviewer_reschedule_notification(interview_staff, interview_date, interview_time, reschedule_reason, count)
        except Exception:
            frappe.log_error(message=traceback.format_exc(), title="Interviewer Reschedule Email/Notification Failed")

    frappe.db.commit()
    return count


def _send_interviewer_reschedule_email(staff_member, interview_date, interview_time, reschedule_reason, applicant_names):
    """Send a combined email to the interviewer with the list of rescheduled students."""
    try:
        template_name = "Interviewer Allocation"
        if not frappe.db.exists("Email Template", template_name):
            return

        staff = frappe.get_doc("Interview Staff Member", staff_member)
        if not staff.email:
            return

        # Fetch details for the rescheduled students
        students = frappe.get_all("Interview Seat Allocation", 
            filters={"name": ["in", applicant_names]},
            fields=["applicant", "candidate_name", "program"]
        )

        if not students:
            return

        template = frappe.get_doc("Email Template", template_name)
        
        args = {
            "staff_name": staff.staff_name,
            "interview_date": interview_date,
            "interview_time": interview_time,
            "interview_address": staff.interview_address,
            "reschedule_reason": reschedule_reason,
            "students": students,
            "is_rescheduled": True
        }

        subject = frappe.render_template(template.subject, args)
        if is_rescheduled_subject := "Rescheduled: " + subject:
            subject = is_rescheduled_subject
            
        message_body = frappe.render_template(template.response_html if template.use_html else template.response, args)

        sender = None
        if template.get("email_account"):
            sender = frappe.db.get_value("Email Account", template.get("email_account"), "email_id") or template.get("email_account")

        frappe.sendmail(
            recipients=[staff.email],
            sender=sender,
            subject=subject,
            message=message_body,
            now=False
        )
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title="Interviewer Reschedule Email Function Failed")


def _send_interviewer_reschedule_notification(staff_member, interview_date, interview_time, reschedule_reason, count):
    """Creates a Notification Log entry for the interviewer regarding rescheduling."""
    try:
        staff = frappe.get_doc("Interview Staff Member", staff_member)
        if not staff.email:
            return
            
        if frappe.db.exists("User", staff.email):
            # Custom message for Interviewer
            message_body = f"""
                <p>The interview schedule for <strong>{count}</strong> students assigned to you has been <strong>rescheduled</strong>.</p>
                <p>New Date: <strong>{format_date(interview_date) or "—"}</strong></p>
                <p>New Time: <strong>{format_time(interview_time) or "—"}</strong></p>
                <p>Venue: <strong>{staff.interview_address or "—"}</strong></p>
                <p>Reason: {reschedule_reason}</p>
                <p>Please check your email for the updated list of students.</p>
            """
            
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": f"Interview Rescheduled: {count} Students",
                "for_user": staff.email,
                "type": "Alert",
                "email_content": message_body,
                "from_user": frappe.session.user
            }).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(message=frappe.get_traceback(), title="Interviewer Reschedule Notification Failed")


def _send_reschedule_email(doc, email):
    """Send an interview reschedule notification email using a configurable template."""
    try:
        template_name = "Interview Reschedule"
        if not frappe.db.exists("Email Template", template_name):
            frappe.log_error(f"Email Template '{template_name}' not found.", "Email Sending Error")
            return

        template = frappe.get_doc("Email Template", template_name)
        
        # Prepare arguments for Jinja
        doc_dict = doc.as_dict()
        args = {
            "doc": doc_dict,
            "portal_url": get_url("/merit-and-scholarship/admission_dashboard?panel=applications")
        }

        subject = frappe.render_template(template.subject, args)
        
        # Determine the content field correctly
        message_body = ""
        if template.get("use_html"):
            message_body = frappe.render_template(template.response_html, args)
        else:
            message_body = frappe.render_template(template.response, args)

        if not message_body:
            message_body = frappe.render_template(template.get("message") or "", args)
            
        # Robust CC handling from the manual 'cc' field added to Email Template
        cc_list = []
        cc_field_value = template.get("cc")
        if cc_field_value:
            # Split by comma or semicolon, strip whitespace, and filter out empties
            cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]
        
        if message_body:
            try:
                # Use now=False to queue the email.
                sender = None
                if template.get("email_account"):
                    sender = frappe.db.get_value("Email Account", template.get("email_account"), "email_id") or template.get("email_account")

                frappe.sendmail(
                    recipients=[email],
                    sender=sender,
                    cc=cc_list,
                    subject=subject,
                    message=message_body,
                    reference_doctype="Interview Seat Allocation",
                    reference_name=doc.name,
                    now=False
                )
                frappe.logger().info(f"Interview Notification Email queued successfully to {email} for {doc.name}")
            except Exception:
                frappe.log_error(traceback.format_exc(), f"Interview Notification Email Queueing Failed: {doc.name}")
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"Interview Reschedule Email Failed: {doc.name}")


def _send_result_notification(doc, email):
    """Creates a Notification Log entry for the interview result."""
    if not email:
        return
    
    if frappe.db.exists("User", email):
        try:
            # Custom message for Interview Result
            message_body = f"""
                <p>Your interview result for <strong>"{doc.interview_list}"</strong> has been published.</p>
                <p><a href="/merit-and-scholarship/admission_dashboard?panel=applications" style="color: #16a34a; font-weight: bold;">Click here to view details.</a></p>
            """
            
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": "Interview Result Published",
                "for_user": email,
                "type": "Alert",
                "email_content": message_body,
                "document_type": "Interview Seat Allocation",
                "document_name": doc.name,
                "from_user": frappe.session.user,
                "link": "/merit-and-scholarship/admission_dashboard?panel=applications"
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(message=frappe.get_traceback(), title=f"Interview Result Notification Failed: {doc.name}")


def _send_reschedule_notification(doc, email):
    """Creates a Notification Log entry for the rescheduled interview."""
    if not email:
        return
    
    if frappe.db.exists("User", email):
        try:
            # Custom message for Interview Reschedule
            message_body = f"""
                <p>Your interview for <strong>"{doc.interview_list}"</strong> has been rescheduled.</p>
                <p>New Date: <strong>{format_date(doc.re_interview_date) or "—"}</strong></p>
                <p>New Time: <strong>{format_time(doc.re_interview_time) or "—"}</strong></p>
                <p><a href="/merit-and-scholarship/admission_dashboard?panel=applications" style="color: #16a34a; font-weight: bold;">Click here to view details.</a></p>
            """
            
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": "Interview Rescheduled",
                "for_user": email,
                "type": "Alert",
                "email_content": message_body,
                "document_type": "Interview Seat Allocation",
                "document_name": doc.name,
                "from_user": frappe.session.user,
                "link": "/merit-and-scholarship/admission_dashboard?panel=applications"
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(message=frappe.get_traceback(), title=f"Interview Reschedule Notification Failed: {doc.name}")


@frappe.whitelist()
def bulk_publish_results(records):
    if isinstance(records, str):
        records = json.loads(records)
    
    count = 0
    for name in records:
        try:
            doc = frappe.get_doc("Interview Seat Allocation", name)
            if not doc.result_published:
                doc.result_published = 1
                doc.save(ignore_permissions=True)
                count += 1
        except Exception as e:
            frappe.log_error(f"Failed to publish Interview Result for {name}: {str(e)}", "Bulk Publish Results Error")
            
    return {"success": True, "count": count}
