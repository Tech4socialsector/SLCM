import frappe
from frappe.utils import now_datetime

no_cache = 1

VENUE_TYPES = [
    "Classroom", "Moot Court", "Open Spaces", "Meeting Room",
    "Mess", "Quad", "Conference Hall", "Project", "Guest House", "Staff Quarters"
]


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "venue_booking"

    student_name = _get_student_name()
    if not student_name:
        context.no_student = True
        _set_nav_defaults(context)
        context.venue_bookings = []
        context.venue_types = VENUE_TYPES
        return context

    context.no_student = False

    try:
        student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
        _set_student_nav(context, student)

        venue_bookings = frappe.get_all(
            "Venue Booking",
            filters={"student": student_name},
            fields=[
                "name", "venue_type", "room", "capacity",
                "start_datetime", "end_datetime", "status",
                "reason", "admin_remarks", "creation"
            ],
            order_by="creation desc",
            limit=100,
            ignore_permissions=True,
        )

        context.venue_bookings = venue_bookings
        context.total_count     = len(venue_bookings)
        context.pending_count   = sum(1 for b in venue_bookings if b.status == "Pending")
        context.approved_count  = sum(1 for b in venue_bookings if b.status == "Approved")
        context.rejected_count  = sum(1 for b in venue_bookings if b.status == "Rejected")
        context.cancelled_count = sum(1 for b in venue_bookings if b.status == "Cancelled")
        context.venue_types     = VENUE_TYPES

    except Exception as e:
        frappe.log_error(f"Venue Booking portal error: {e}", "Student Portal")
        context.portal_error = str(e)
        _set_nav_defaults(context)
        context.venue_bookings = []
        context.venue_types    = VENUE_TYPES

    return context



def _get_student_name():
    user = frappe.session.user
    name = frappe.db.get_value("Student Master", {"user": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"email": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"official_email_id": user}, "name")
    if name:
        try:
            current_user = frappe.db.get_value("Student Master", name, "user")
            if not current_user:
                frappe.db.set_value("Student Master", name, "user", user, update_modified=False)
        except Exception:
            pass
    return name


def _set_student_nav(context, student):
    full_name = " ".join(filter(None, [student.first_name, student.middle_name, student.last_name]))
    context.student_name   = full_name or student.name
    context.student_id     = student.registration_id or student.name
    context.student_photo  = student.passport_size_photo or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    context.programme_name = frappe.db.get_value("Cohort", student.programme, "cohort_name") or student.programme or ""
    context.department     = student.department or ""
    context.batch_year     = student.batch_year or ""


def _set_nav_defaults(context):
    user     = frappe.session.user
    user_doc = frappe.db.get_value("User", user, ["full_name", "user_image"], as_dict=True)
    context.student_name   = (user_doc.full_name if user_doc else "") or user.split("@")[0]
    context.student_id     = ""
    context.student_photo  = (user_doc.user_image if user_doc else "") or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    context.programme_name = ""
    context.department     = ""
    context.batch_year     = ""
