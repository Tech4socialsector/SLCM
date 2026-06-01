import frappe
from slcm.utils.faculty_portal import get_faculty_name, set_faculty_nav, set_nav_defaults

no_cache = 1


def get_context(context):
    context.no_cache = 1
    _set_defaults(context)

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "venue_booking"

    faculty_name = get_faculty_name()
    if not faculty_name:
        context.not_a_faculty = True
        set_nav_defaults(context)
        _set_defaults(context)
        return context

    context.not_a_faculty = False

    try:
        faculty = frappe.get_doc("Faculty", faculty_name, ignore_permissions=True)
        set_faculty_nav(context, faculty)

        # ── My bookings ─────────────────────────────────────────────
        my_bookings = frappe.get_all(
            "Venue Booking",
            filters={"requester_name": faculty_name},
            fields=["name", "event_name", "venue_type", "room",
                    "start_datetime", "end_datetime", "status",
                    "expected_attendees", "reason", "admin_remarks"],
            order_by="start_datetime desc",
            limit=40,
            ignore_permissions=True,
        )

        for b in my_bookings:
            b["start_fmt"] = frappe.utils.format_datetime(b.start_datetime, "dd MMM yyyy, hh:mm a") if b.start_datetime else "—"
            b["end_fmt"]   = frappe.utils.format_datetime(b.end_datetime, "hh:mm a") if b.end_datetime else "—"
            status = b.status or "Pending"
            b["status_class"] = {
                "Pending":  "fp-badge-warning",
                "Approved": "fp-badge-success",
                "Rejected": "fp-badge-danger",
                "Cancelled": "fp-badge-neutral",
            }.get(status, "fp-badge-neutral")

        context.my_bookings = my_bookings

        # ── Stats ────────────────────────────────────────────────────
        context.total_bookings = len(my_bookings)
        context.pending_bookings = sum(1 for b in my_bookings if (b.status or "Pending") == "Pending")
        context.approved_bookings = sum(1 for b in my_bookings if b.status == "Approved")
        context.rejected_bookings = sum(1 for b in my_bookings if b.status == "Rejected")

        # ── Available rooms ──────────────────────────────────────────
        try:
            rooms = frappe.get_all(
                "Room",
                filters={"is_booking_allowed": 1},
                fields=["name", "room_name", "room_number", "seating_capacity", "room_type"],
                order_by="room_name asc",
                ignore_permissions=True,
            )
        except Exception:
            rooms = []
        context.available_rooms = rooms

    except Exception as e:
        frappe.log_error(f"Faculty Portal Venue Booking error: {e}", "Faculty Portal")
        context.portal_error = str(e)
        set_nav_defaults(context)
        _set_defaults(context)

    return context


def _set_defaults(context):
    context.my_bookings = []
    context.total_bookings = 0
    context.pending_bookings = 0
    context.approved_bookings = 0
    context.rejected_bookings = 0
    context.available_rooms = []
