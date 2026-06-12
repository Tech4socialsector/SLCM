import json
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import get_datetime


class VenueBooking(Document):
	def before_insert(self):
		self._set_requester_info()

	def validate(self):
		self.validate_dates()
		self.check_availability()
		self._protect_status_field()

	def _protect_status_field(self):
		"""Prevent non-admin users from changing the status field directly."""
		if self.is_new():
			# New docs always start as Pending — reset if someone tried to set it
			self.status = "Pending"
			return

		admin_roles = {"System Manager", "Administrator", "slcm_Registrar"}
		user_roles = set(frappe.get_roles(frappe.session.user))
		if admin_roles & user_roles:
			return  # Admins may change status freely

		# For non-admins, revert any status change back to the saved value
		saved_status = frappe.db.get_value("Venue Booking", self.name, "status")
		if saved_status and self.status != saved_status:
			frappe.throw(
				_("You are not allowed to change the booking status. Only Admin can approve, reject, or cancel bookings."),
				frappe.PermissionError
			)

	def after_insert(self):
		_notify_admin_new_booking(self)

	def validate_dates(self):
		if get_datetime(self.start_datetime) >= get_datetime(self.end_datetime):
			frappe.throw(_("End Date & Time must be after Start Date & Time"))

	def check_availability(self):
		if not self.room:
			return

		is_allowed = frappe.db.get_value("Room", self.room, "is_booking_allowed")
		if not is_allowed:
			frappe.throw(_("Booking is not allowed for this Room: {0}").format(self.room))

		overlap = frappe.db.sql("""
			SELECT name FROM `tabVenue Booking`
			WHERE room = %s
			AND docstatus < 2
			AND name != %s
			AND status NOT IN ('Cancelled', 'Rejected')
			AND (
				(start_datetime > %s AND start_datetime < %s) OR
				(end_datetime > %s AND end_datetime < %s) OR
				(start_datetime <= %s AND end_datetime >= %s)
			)
		""", (self.room, self.name or "New Venue Booking",
			self.start_datetime, self.end_datetime,
			self.start_datetime, self.end_datetime,
			self.start_datetime, self.end_datetime))

		if overlap:
			frappe.throw(_("Room {0} is already booked during this period (Ref: {1})").format(
				self.room, overlap[0][0]))

	def _set_requester_info(self):
		"""Auto-fill requester_name and requester_type from the logged-in user."""
		user = frappe.session.user
		if not self.requester_name:
			full_name = frappe.db.get_value("User", user, "full_name") or user
			self.requester_name = full_name

		if not self.requester_type:
			roles = set(frappe.get_roles(user))
			if "slcm_Student" in roles:
				self.requester_type = "Student"
			elif "slcm_Faculty" in roles:
				self.requester_type = "Faculty"
			elif "slcm_Staff" in roles:
				self.requester_type = "Staff"
			else:
				self.requester_type = "Other"

		# Auto-link student record if requester is a student
		if not self.student and self.requester_type == "Student":
			student = _get_student_for_user(user)
			if student:
				self.student = student


# ─────────────────────────────────────────────────────────────────────────────
#  Room query helper
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_room_query(doctype, txt, searchfield, start, page_len, filters):
	filters_dict = {}
	if hasattr(filters, 'get'):
		filters_dict = filters
	elif isinstance(filters, str):
		filters_dict = json.loads(filters)

	conditions = []
	values = []
	if filters_dict.get('venue_type'):
		conditions.append("room_type = %s")
		values.append(filters_dict['venue_type'])

	if txt:
		conditions.append("room_name LIKE %s")
		values.append("%" + txt + "%")

	where_clause = ""
	if conditions:
		where_clause = "WHERE " + " AND ".join(conditions)

	return frappe.db.sql("""
		SELECT name, room_name, seating_capacity
		FROM `tabRoom`
		{where_clause}
		LIMIT %s, %s
	""".format(where_clause=where_clause), tuple(values + [int(start), int(page_len)]))


# ─────────────────────────────────────────────────────────────────────────────
#  Admin actions (approve / reject / cancel / swap)
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def approve_booking(booking_name, admin_remarks=None):
	_require_admin()
	booking = frappe.get_doc("Venue Booking", booking_name)
	if booking.status != "Pending":
		frappe.throw(_("Only Pending bookings can be approved."))
	frappe.db.set_value("Venue Booking", booking_name, {
		"status": "Approved",
		"admin_remarks": admin_remarks or ""
	})
	frappe.db.commit()
	_notify_requester(booking_name, "Approved", admin_remarks)
	return {"status": "Approved"}


@frappe.whitelist()
def reject_booking(booking_name, admin_remarks=None):
	_require_admin()
	booking = frappe.get_doc("Venue Booking", booking_name)
	if booking.status != "Pending":
		frappe.throw(_("Only Pending bookings can be rejected."))
	frappe.db.set_value("Venue Booking", booking_name, {
		"status": "Rejected",
		"admin_remarks": admin_remarks or ""
	})
	frappe.db.commit()
	_notify_requester(booking_name, "Rejected", admin_remarks)
	return {"status": "Rejected"}


@frappe.whitelist()
def cancel_booking(booking_name, admin_remarks=None):
	_require_admin()
	booking = frappe.get_doc("Venue Booking", booking_name)
	if booking.status == "Cancelled":
		frappe.throw(_("Booking is already cancelled."))
	frappe.db.set_value("Venue Booking", booking_name, {
		"status": "Cancelled",
		"admin_remarks": admin_remarks or ""
	})
	frappe.db.commit()
	_notify_requester(booking_name, "Cancelled", admin_remarks)
	return {"status": "Cancelled"}


@frappe.whitelist()
def approve_venue_swap(booking_name, admin_remarks=None):
    """Admin approves a student's swap request — moves the booking to the requested room."""
    _require_admin()

    booking = frappe.get_doc("Venue Booking", booking_name, ignore_permissions=True)

    if not booking.swap_requested or booking.swap_status != "Pending":
        frappe.throw(_("No pending swap request found for this booking."))

    new_room = booking.swap_requested_room
    if not new_room:
        frappe.throw(_("Swap request has no target room specified."))

    # Conflict check: can the booking move to the new room?
    try:
        check_conflict(booking, new_room)
    except Exception as e:
        frappe.throw(_("Cannot approve swap — {0}").format(str(e)))

    old_room = booking.room
    decided_by = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user

    frappe.db.set_value("Venue Booking", booking_name, {
        "room":                new_room,
        "swap_requested":      0,
        "swap_status":         "Approved",
        "swap_admin_remarks":  admin_remarks or "",
    }, update_modified=False)

    frappe.db.sql("""
        UPDATE `tabVenue Swap Log`
        SET swap_status    = 'Approved',
            decided_on     = %(now)s,
            decided_by     = %(by)s,
            admin_remarks  = %(remarks)s,
            modified       = %(now)s
        WHERE parent = %(parent)s
          AND swap_status = 'Pending'
        ORDER BY idx DESC
        LIMIT 1
    """, {"parent": booking_name, "now": frappe.utils.now(),
          "by": decided_by, "remarks": admin_remarks or ""})
    frappe.db.commit()

    _notify_requester_swap(booking_name, "Approved", old_room, new_room, admin_remarks)
    return {"status": "swap_approved", "new_room": new_room}


@frappe.whitelist()
def reject_venue_swap(booking_name, admin_remarks=None):
    """Admin rejects a student's swap request — booking stays in the current room."""
    _require_admin()

    booking = frappe.get_doc("Venue Booking", booking_name, ignore_permissions=True)

    if not booking.swap_requested or booking.swap_status != "Pending":
        frappe.throw(_("No pending swap request found for this booking."))

    decided_by = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user

    frappe.db.set_value("Venue Booking", booking_name, {
        "swap_requested":     0,
        "swap_status":        "Rejected",
        "swap_admin_remarks": admin_remarks or "",
    }, update_modified=False)

    frappe.db.sql("""
        UPDATE `tabVenue Swap Log`
        SET swap_status    = 'Rejected',
            decided_on     = %(now)s,
            decided_by     = %(by)s,
            admin_remarks  = %(remarks)s,
            modified       = %(now)s
        WHERE parent = %(parent)s
          AND swap_status = 'Pending'
        ORDER BY idx DESC
        LIMIT 1
    """, {"parent": booking_name, "now": frappe.utils.now(),
          "by": decided_by, "remarks": admin_remarks or ""})
    frappe.db.commit()

    _notify_requester_swap(booking_name, "Rejected",
                           booking.room, booking.swap_requested_room, admin_remarks)
    return {"status": "swap_rejected"}


def _notify_requester_swap(booking_name, decision, old_room, new_room, admin_remarks=None):
    """Email the requester when their swap request is approved or rejected."""
    try:
        doc = frappe.db.get_value(
            "Venue Booking", booking_name,
            ["owner", "event_name", "requester_name", "start_datetime", "end_datetime"],
            as_dict=True,
        )
        if not doc:
            return

        requester_email = frappe.db.get_value("User", doc.owner, "email")
        if not requester_email:
            return

        new_room_name = frappe.db.get_value("Room", new_room, "room_name") or new_room or "—"
        color = "#166534" if decision == "Approved" else "#991b1b"
        bg    = "#f0fdf4" if decision == "Approved" else "#fef2f2"

        subject = f"[Venue Booking] Swap Request {decision}: {doc.event_name}"
        body_detail = (
            f"Your venue has been moved from <strong>{old_room}</strong> to <strong>{new_room_name}</strong>."
            if decision == "Approved"
            else f"Your request to move to <strong>{new_room_name}</strong> was not approved. Your booking remains in <strong>{old_room}</strong>."
        )
        message = f"""
<p>Hi {doc.requester_name or 'there'},</p>
<p>Your venue swap request has been <strong style="color:{color};">{decision.lower()}</strong>.</p>
<div style="background:{bg};border-radius:8px;padding:16px 20px;margin:16px 0;font-size:14px;">
  <table style="border-collapse:collapse;width:100%;">
    <tr><td style="padding:4px 0;font-weight:600;color:#555;width:160px;">Booking Ref</td><td style="padding:4px 0;">{booking_name}</td></tr>
    <tr><td style="padding:4px 0;font-weight:600;color:#555;">Event</td><td style="padding:4px 0;">{doc.event_name}</td></tr>
    <tr><td style="padding:4px 0;font-weight:600;color:#555;">Time Slot</td><td style="padding:4px 0;">{doc.start_datetime} → {doc.end_datetime}</td></tr>
    <tr><td style="padding:4px 0;font-weight:600;color:#555;">Decision</td><td style="padding:4px 0;font-weight:700;color:{color};">{decision}</td></tr>
    {f'<tr><td style="padding:4px 0;font-weight:600;color:#555;">Admin Remarks</td><td style="padding:4px 0;">{admin_remarks}</td></tr>' if admin_remarks else ""}
  </table>
  <p style="margin-top:10px;font-size:13px;">{body_detail}</p>
</div>
"""
        frappe.sendmail(recipients=[requester_email], subject=subject, message=message, now=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Venue Swap — Requester Notification Error")


@frappe.whitelist()
def swap_venue(booking_a, booking_b):
	if not booking_a or not booking_b:
		frappe.throw(_("Both bookings are required for swapping."))

	doc_a = frappe.get_doc("Venue Booking", booking_a)
	doc_b = frappe.get_doc("Venue Booking", booking_b)

	if doc_a.docstatus == 2 or doc_b.docstatus == 2:
		frappe.throw(_("Cannot swap cancelled bookings."))

	room_a = doc_a.room
	room_b = doc_b.room

	if room_a == room_b:
		frappe.throw(_("Both bookings are already for the same room."))

	try:
		check_conflict(doc_a, room_b, exclude_booking=doc_b.name)
		check_conflict(doc_b, room_a, exclude_booking=doc_a.name)

		frappe.db.set_value("Venue Booking", doc_a.name, "room", room_b)
		frappe.db.set_value("Venue Booking", doc_b.name, "room", room_a)

		doc_a.reload()
		doc_b.reload()

		frappe.msgprint(_("Venues swapped successfully: {0} ↔ {1}").format(room_a, room_b))

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Venue Swap Error")
		frappe.throw(_("Could not swap venues: {0}").format(str(e)))


def check_conflict(booking_doc, new_room, exclude_booking=None):
	existing = frappe.db.sql("""
		SELECT name FROM `tabVenue Booking`
		WHERE room = %s
		AND docstatus < 2
		AND name != %s
		AND name != %s
		AND status NOT IN ('Cancelled', 'Rejected')
		AND (
			(start_datetime > %s AND start_datetime < %s) OR
			(end_datetime > %s AND end_datetime < %s) OR
			(start_datetime <= %s AND end_datetime >= %s)
		)
	""", (new_room, booking_doc.name, exclude_booking or "",
		booking_doc.start_datetime, booking_doc.end_datetime,
		booking_doc.start_datetime, booking_doc.end_datetime,
		booking_doc.start_datetime, booking_doc.end_datetime))

	if existing:
		frappe.throw(_("Booking {0} cannot move to Room {1} — conflicts with {2}").format(
			booking_doc.name, new_room, existing[0][0]))


# ─────────────────────────────────────────────────────────────────────────────
#  Calendar availability (used by desk calendar view or external queries)
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_room_bookings(room=None, from_date=None, to_date=None):
	"""Return bookings for calendar display. Optionally filter by room and date range."""
	filters = [["status", "not in", ["Cancelled", "Rejected"]], ["docstatus", "<", 2]]
	if room:
		filters.append(["room", "=", room])
	if from_date:
		filters.append(["start_datetime", ">=", from_date])
	if to_date:
		filters.append(["end_datetime", "<=", to_date])

	return frappe.get_all(
		"Venue Booking",
		filters=filters,
		fields=[
			"name", "event_name", "room", "venue_type",
			"start_datetime", "end_datetime", "status",
			"requester_name", "requester_type"
		],
		order_by="start_datetime asc",
		ignore_permissions=True,
	)


# ─────────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _require_admin():
	allowed_roles = {"System Manager", "Administrator", "slcm_Registrar"}
	user_roles = set(frappe.get_roles(frappe.session.user))
	if not (allowed_roles & user_roles):
		frappe.throw(_("You do not have permission to perform this action."), frappe.PermissionError)


def _get_student_for_user(user):
	name = frappe.db.get_value("Student Master", {"user": user}, "name")
	if not name:
		name = frappe.db.get_value("Student Master", {"email": user}, "name")
	if not name:
		name = frappe.db.get_value("Student Master", {"official_email_id": user}, "name")
	return name


def _notify_admin_new_booking(doc):
	"""Email the admin/registrar when a new booking is submitted."""
	try:
		admin_roles = ["slcm_Registrar", "System Manager"]
		admin_emails = []
		for role in admin_roles:
			users = frappe.get_all(
				"Has Role",
				filters={"role": role, "parenttype": "User"},
				fields=["parent"],
				ignore_permissions=True,
			)
			for u in users:
				email = frappe.db.get_value("User", u.parent, "email")
				if email and email not in admin_emails:
					admin_emails.append(email)

		if not admin_emails:
			return

		# requester_name now stores the display name directly
		requester_display = doc.requester_name or "—"

		# Build direct approval link to the Venue Booking desk form
		site_url = frappe.utils.get_url()
		booking_url = f"{site_url}/app/venue-booking/{doc.name}"

		subject = f"[Venue Booking] New Request: {doc.event_name} — {doc.room}"
		message = f"""
<p>A new venue booking has been submitted and requires your review.</p>
<table style="border-collapse:collapse;width:100%;font-size:14px;">
  <tr><td style="padding:6px 12px;font-weight:600;color:#555;width:160px;">Reference</td><td style="padding:6px 12px;">{doc.name}</td></tr>
  <tr style="background:#f7f7f7;"><td style="padding:6px 12px;font-weight:600;color:#555;">Event / Purpose</td><td style="padding:6px 12px;">{doc.event_name}</td></tr>
  <tr><td style="padding:6px 12px;font-weight:600;color:#555;">Requested By</td><td style="padding:6px 12px;">{requester_display} ({doc.requester_type})</td></tr>
  <tr style="background:#f7f7f7;"><td style="padding:6px 12px;font-weight:600;color:#555;">Venue</td><td style="padding:6px 12px;">{doc.room} ({doc.venue_type})</td></tr>
  <tr><td style="padding:6px 12px;font-weight:600;color:#555;">Start</td><td style="padding:6px 12px;">{doc.start_datetime}</td></tr>
  <tr style="background:#f7f7f7;"><td style="padding:6px 12px;font-weight:600;color:#555;">End</td><td style="padding:6px 12px;">{doc.end_datetime}</td></tr>
  {f'<tr><td style="padding:6px 12px;font-weight:600;color:#555;">Attendees</td><td style="padding:6px 12px;">{doc.expected_attendees}</td></tr>' if doc.expected_attendees else ""}
  {f'<tr style="background:#f7f7f7;"><td style="padding:6px 12px;font-weight:600;color:#555;">Remarks</td><td style="padding:6px 12px;">{doc.reason}</td></tr>' if doc.reason else ""}
</table>
<p style="margin-top:20px;">
  <a href="{booking_url}"
     style="display:inline-block;padding:10px 24px;background:#1e3a5f;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;font-size:14px;">
    Review &amp; Approve / Reject
  </a>
</p>
<p style="font-size:12px;color:#888;margin-top:8px;">
  Or copy this link: <a href="{booking_url}" style="color:#1e3a5f;">{booking_url}</a>
</p>
"""
		frappe.sendmail(
			recipients=admin_emails,
			subject=subject,
			message=message,
			now=True,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Venue Booking — Admin Notification Error")


def _notify_requester(booking_name, new_status, admin_remarks=None):
	"""Email the booking owner when their request is approved, rejected, or cancelled."""
	try:
		doc = frappe.db.get_value(
			"Venue Booking", booking_name,
			["owner", "event_name", "room", "venue_type", "start_datetime", "end_datetime", "requester_name"],
			as_dict=True,
		)
		if not doc:
			return

		requester_email = frappe.db.get_value("User", doc.owner, "email")
		if not requester_email:
			return

		status_colors = {
			"Approved": "#166534",
			"Rejected": "#991b1b",
			"Cancelled": "#374151",
		}
		status_bg = {
			"Approved": "#f0fdf4",
			"Rejected": "#fef2f2",
			"Cancelled": "#f3f4f6",
		}
		color = status_colors.get(new_status, "#374151")
		bg    = status_bg.get(new_status, "#f3f4f6")

		subject = f"[Venue Booking] {new_status}: {doc.event_name} — {doc.room}"
		message = f"""
<p>Hi {doc.requester_name or 'there'},</p>
<p>Your venue booking request has been <strong style="color:{color};">{new_status.lower()}</strong>.</p>
<div style="background:{bg};border-radius:8px;padding:16px 20px;margin:16px 0;font-size:14px;">
  <table style="border-collapse:collapse;width:100%;">
    <tr><td style="padding:4px 0;font-weight:600;color:#555;width:140px;">Reference</td><td style="padding:4px 0;">{booking_name}</td></tr>
    <tr><td style="padding:4px 0;font-weight:600;color:#555;">Event</td><td style="padding:4px 0;">{doc.event_name}</td></tr>
    <tr><td style="padding:4px 0;font-weight:600;color:#555;">Venue</td><td style="padding:4px 0;">{doc.room} ({doc.venue_type})</td></tr>
    <tr><td style="padding:4px 0;font-weight:600;color:#555;">From</td><td style="padding:4px 0;">{doc.start_datetime}</td></tr>
    <tr><td style="padding:4px 0;font-weight:600;color:#555;">To</td><td style="padding:4px 0;">{doc.end_datetime}</td></tr>
    <tr><td style="padding:4px 0;font-weight:600;color:#555;">Status</td>
        <td style="padding:4px 0;font-weight:700;color:{color};">{new_status}</td></tr>
    {f'<tr><td style="padding:4px 0;font-weight:600;color:#555;">Admin Remarks</td><td style="padding:4px 0;">{admin_remarks}</td></tr>' if admin_remarks else ""}
  </table>
</div>
<p style="font-size:13px;color:#666;">
  {"Your booking is confirmed. Please ensure the venue is kept clean after use." if new_status == "Approved"
   else "If you have any questions, please contact the administration." }
</p>
"""
		frappe.sendmail(
			recipients=[requester_email],
			subject=subject,
			message=message,
			now=True,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Venue Booking — Requester Notification Error")
