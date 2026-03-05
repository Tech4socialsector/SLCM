import frappe
from frappe import _
from frappe.utils import formatdate, format_datetime, nowdate

def get_context(context):
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please login to view this page"), frappe.PermissionError)

    # Get applicant for the current user
    applicant_name = frappe.db.get_value("Applicant", {"email": user}, "name")
    if not applicant_name:
        context.no_record = True
        return context

    # Get Interview Seat Allocation record
    allocation = frappe.get_all(
        "Interview Seat Allocation",
        filters={"applicant": applicant_name},
        fields=["*"],
        order_by="creation desc",
        limit=1
    )

    if not allocation:
        context.no_record = True
        return context

    doc = frappe.get_doc("Interview Seat Allocation", allocation[0].name)
    context.doc = doc

    # Determine rescheduled state
    is_rescheduled = (doc.is_rescheduled == 1 or doc.interview_slot_status == "Rescheduled")
    context.is_rescheduled = is_rescheduled

    if is_rescheduled:
        context.previous_schedule = {
            "staff_name": doc.staff_name,
            "interview_date": doc.interview_date,
            "interview_time": doc.interview_time,
            "interview_address": doc.interview_address,
            "reason": doc.reschedule_reason or "System Rescheduled"
        }
    else:
        context.previous_schedule = None

    # Pick which slot data to show
    if is_rescheduled:
        context.current_slot = {
            "staff_name": doc.re_staff_name,
            "staff_email": doc.re_staff_email,
            "staff_contact": doc.re_staff_contact,
            "interview_date": doc.re_interview_date,
            "interview_time": doc.re_interview_time,
            "interview_address": doc.re_interview_address,
            "slot_status": doc.re_interview_slot_status,
            "attendance_confirmation": doc.re_interview_attendance_confirmation,
        }
    else:
        context.current_slot = {
            "staff_name": doc.staff_name,
            "staff_email": doc.staff_email,
            "staff_contact": doc.staff_contact,
            "interview_date": doc.interview_date,
            "interview_time": doc.interview_time,
            "interview_address": doc.interview_address,
            "slot_status": doc.interview_slot_status,
            "attendance_confirmation": doc.interview_attendance_confirmation,
        }

    # Show result section when result is published and attendance recorded
    context.show_result = (
        doc.interview_status in ["Attended", "Absent", "Selected", "Rejected", "Withheld"]
        and doc.result_published == 1
    )

    # Whether feedback form should appear (result published)
    context.show_feedback = (doc.result_published == 1)
    context.feedback_submitted = bool(doc.feedback)

    # Attendance options
    context.attendance_options = ["Will Attend", "Will Not Attend", "Need Reschedule"]

    return context


@frappe.whitelist()
def save_attendance_confirmation(allocation_name, confirmation, is_rescheduled=False):
    """
    Saves the applicant's attendance confirmation for the interview.
    Allowed options: Will Attend, Will Not Attend, Need Reschedule
    """
    allowed = ["Will Attend", "Will Not Attend", "Need Reschedule"]
    if confirmation not in allowed:
        frappe.throw(_("Invalid confirmation option."))

    # Security check: verify ownership
    owner_email = frappe.db.get_value("Interview Seat Allocation", allocation_name, "email")
    if owner_email != frappe.session.user:
        frappe.throw(_("You are not authorized to modify this record."), frappe.PermissionError)

    if isinstance(is_rescheduled, str):
        is_rescheduled = is_rescheduled.lower() == "true"

    doc = frappe.get_doc("Interview Seat Allocation", allocation_name)

    if is_rescheduled:
        doc.re_interview_attendance_confirmation = confirmation
    else:
        doc.interview_attendance_confirmation = confirmation

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "confirmation": confirmation}


@frappe.whitelist()
def save_feedback(allocation_name, feedback_text):
    """
    Saves the applicant's feedback after result is published.
    """
    if not feedback_text or not feedback_text.strip():
        frappe.throw(_("Feedback cannot be empty."))

    # Security check
    owner_email = frappe.db.get_value("Interview Seat Allocation", allocation_name, "email")
    if owner_email != frappe.session.user:
        frappe.throw(_("You are not authorized to modify this record."), frappe.PermissionError)

    doc = frappe.get_doc("Interview Seat Allocation", allocation_name)

    if not doc.result_published:
        frappe.throw(_("Feedback can only be submitted after the result has been published."))

    doc.feedback = feedback_text.strip()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}
