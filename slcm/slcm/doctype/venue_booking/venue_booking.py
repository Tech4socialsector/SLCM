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
		"""
		Check if the room is available for the given time slot.
		"""
		if not self.room:
			return

		# Check if Room is booking allowed
		is_allowed = frappe.db.get_value("Room", self.room, "is_booking_allowed")
		if not is_allowed:
			frappe.throw(_("Booking is not allowed for this Room: {0}").format(self.room))

		# Check for overlapping Venue Bookings
		overlap = frappe.db.sql("""
			SELECT name FROM `tabVenue Booking`
			WHERE room = %s
			AND docstatus < 2
			AND name != %s
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
	"""
	Filter Rooms based on Venue Type if selected.
	"""
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
def swap_venue(booking_a, booking_b):
	"""
	Swap rooms between two Venue Bookings.
	"""
	if not booking_a or not booking_b:
		frappe.throw(_("Both bookings are required for swapping."))

	doc_a = frappe.get_doc("Venue Booking", booking_a)
	doc_b = frappe.get_doc("Venue Booking", booking_b)

	# Verify if both bookings are valid and not cancelled
	if doc_a.docstatus == 2 or doc_b.docstatus == 2:
		frappe.throw(_("Cannot swap cancelled bookings."))

	room_a = doc_a.room
	room_b = doc_b.room

	if room_a == room_b:
		frappe.throw(_("Both bookings are already for the same room."))

	# Basic Capacity Check (Optional, depending on user strictness)
	# if doc_a.capacity > frappe.db.get_value("Room", room_b, "seating_capacity"): ... 
	# For now, we assume admin knows what they are doing or we let the validate method handle it if we re-save.
	
	# Swap rooms
	doc_a.room = room_b
	doc_b.room = room_a

	# We need to bypass the overlap check because technically during the swap instant, 
	# if we save one, it might conflict with the other if times overlap precisely.
	# However, since we are swapping A to B and B to A, and assuming A and B were valid before, 
	# the ONLY conflict that could arise is if A's new room (B's old room) has *another* booking C that overlaps with A's time but didn't overlap with B's time?
	# Wait, if B was valid in Room B, then Room B is free for B's time.
	# If A's time != B's time, then putting A in Room B might conflict with a third booking D in Room B.
	# So we MUST run validation.

	# But what if A and B have the SAME time?
	# Then swapping is safe from third-party conflicts, but we need to match them carefully.
	
	# Let's try to save. The `check_availability` logic in `validate` will run.
	# If A and B overlap in time, `doc_a.save()` checks Room B. Doc B is still holding Room B until `doc_b.save()`?
	# No, `doc_b` is in DB with Room B. `doc_a` trying to take Room B will fail validation because `doc_b` (in DB) holds it.
	
	# Solution: Use a custom flag to ignore self-conflict or specific cross-conflict during validation?
	# Or, use `flags.ignore_validate = True` and manually check conflicts excluding the other swapping doc?
	
	# Better approach for atomic swap of same-time bookings:
	# 1. Update DB directly for one to a temporary placeholder? No, referential integrity.
	# 2. If times are identical, we can use `flags.ignore_validate`.
	# 3. If times are different, standard validation should apply, but we need to temporarily "free" the rooms.

	# Let's try a transaction where we temporarily set rooms to None (if allowed) or a dummy?
	# Or, we allow the save if the conflicting booking is the one we are swapping with.
	
	# Let's modify `check_availability` to accept an exclusion list?
	# Or just do it manually here.
	
	try:
		# Bypass standard validation for the swap operation regarding strictly these two docs
		# We still want to check against *other* bookings.
		
		# Validation for A in Room B (Excluding B)
		check_conflict(doc_a, room_b, exclude_booking=doc_b.name)
		# Validation for B in Room A (Excluding A)
		check_conflict(doc_b, room_a, exclude_booking=doc_a.name)

		# If clean, update DB
		frappe.db.set_value("Venue Booking", doc_a.name, "room", room_b)
		frappe.db.set_value("Venue Booking", doc_b.name, "room", room_a)
		
		# Update timestamp/modified
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
		frappe.throw(_("Detailed Conflict: Booking {0} cannot move to Room {1} because it overlaps with {2}").format(booking_doc.name, new_room, existing[0][0]))

