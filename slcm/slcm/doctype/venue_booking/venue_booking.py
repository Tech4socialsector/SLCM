import json
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import get_datetime

class VenueBooking(Document):
	def validate(self):
		self.validate_dates()
		self.check_availability()

	def validate_dates(self):
		if get_datetime(self.start_datetime) >= get_datetime(self.end_datetime):
			frappe.throw(_("End Date must be greater than Start Date"))

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
			AND status != 'Cancelled'
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
			frappe.throw(_("Room {0} is already booked during this period by {1}").format(self.room, overlap[0][0]))


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


@frappe.whitelist()
def approve_booking(booking_name, admin_remarks=None):
	_require_admin_or_faculty()
	booking = frappe.get_doc("Venue Booking", booking_name)
	if booking.status != "Pending":
		frappe.throw(_("Only Pending bookings can be approved."))
	frappe.db.set_value("Venue Booking", booking_name, {
		"status": "Approved",
		"admin_remarks": admin_remarks or ""
	})
	frappe.db.commit()
	return {"status": "Approved"}


@frappe.whitelist()
def reject_booking(booking_name, admin_remarks=None):
	_require_admin_or_faculty()
	booking = frappe.get_doc("Venue Booking", booking_name)
	if booking.status != "Pending":
		frappe.throw(_("Only Pending bookings can be rejected."))
	frappe.db.set_value("Venue Booking", booking_name, {
		"status": "Rejected",
		"admin_remarks": admin_remarks or ""
	})
	frappe.db.commit()
	return {"status": "Rejected"}


@frappe.whitelist()
def cancel_booking(booking_name, admin_remarks=None):
	_require_admin_or_faculty()
	booking = frappe.get_doc("Venue Booking", booking_name)
	if booking.status == "Cancelled":
		frappe.throw(_("Booking is already cancelled."))
	frappe.db.set_value("Venue Booking", booking_name, {
		"status": "Cancelled",
		"admin_remarks": admin_remarks or ""
	})
	frappe.db.commit()
	return {"status": "Cancelled"}


def _require_admin_or_faculty():
	allowed_roles = {"System Manager", "Administrator", "slcm_Faculty", "slcm_Registrar"}
	user_roles = set(frappe.get_roles(frappe.session.user))
	if not (allowed_roles & user_roles):
		frappe.throw(_("You do not have permission to perform this action."), frappe.PermissionError)


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

		frappe.msgprint(_("Venues swapped successfully: {0} <-> {1}").format(room_a, room_b))

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
		AND status != 'Cancelled'
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
		frappe.throw(_("Booking {0} cannot move to Room {1} because it overlaps with {2}").format(
			booking_doc.name, new_room, existing[0][0]))
