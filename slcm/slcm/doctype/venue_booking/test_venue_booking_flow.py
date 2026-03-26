import frappe
from frappe.utils import add_days, now_datetime

def test_venue_booking_flow():
	frappe.set_user("Administrator")
	
	# 1. Setup Rooms
	if not frappe.db.exists("Room", "Classroom A"):
		frappe.get_doc({
			"doctype": "Room",
			"room_name": "Classroom A",
			"room_number": "101",
			"room_type": "Classroom",
			"seating_capacity": 50,
			"is_booking_allowed": 1
		}).insert()

	if not frappe.db.exists("Room", "Classroom B"):
		frappe.get_doc({
			"doctype": "Room",
			"room_name": "Classroom B",
			"room_number": "102",
			"room_type": "Classroom",
			"seating_capacity": 60,
			"is_booking_allowed": 1
		}).insert()

	# Cleanup previous test data
	frappe.db.delete("Venue Booking", {"room": ["in", ["Classroom A", "Classroom B"]]})
	
	start = now_datetime()
	end = add_days(start, 0)
	end = end.replace(hour=start.hour + 1) # 1 hour booking

	print(f"Testing Booking for: {start} to {end}")

	# 2. Create Booking A in Classroom A
	booking_a = frappe.get_doc({
		"doctype": "Venue Booking",
		"venue_type": "Classroom",
		"room": "Classroom A",
		"start_datetime": start,
		"end_datetime": end,
		"reason": "Test Booking A"
	}).insert()
	print(f"Created Booking A: {booking_a.name} in {booking_a.room}")

	# 3. Create Booking B in Classroom B (Same time)
	booking_b = frappe.get_doc({
		"doctype": "Venue Booking",
		"venue_type": "Classroom",
		"room": "Classroom B",
		"start_datetime": start,
		"end_datetime": end,
		"reason": "Test Booking B"
	}).insert()
	print(f"Created Booking B: {booking_b.name} in {booking_b.room}")

	# 4. Try to create Booking C in Classroom A (Should Fail)
	try:
		frappe.get_doc({
			"doctype": "Venue Booking",
			"venue_type": "Classroom",
			"room": "Classroom A",
			"start_datetime": start,
			"end_datetime": end,
			"reason": "Test Booking C (Conflict)"
		}).insert()
		print("ERROR: Booking C should have failed due to conflict!")
	except Exception as e:
		print("Success: Booking C failed as expected.")

	# 5. Swap A and B
	from slcm.slcm.doctype.venue_booking.venue_booking import swap_venue
	print("Swapping Venue Booking A and B...")
	swap_venue(booking_a.name, booking_b.name)
	
	# Reload
	booking_a.reload()
	booking_b.reload()
	
	print(f"After Swap -> Booking A is in: {booking_a.room}")
	print(f"After Swap -> Booking B is in: {booking_b.room}")

	if booking_a.room == "Classroom B" and booking_b.room == "Classroom A":
		print("SUCCESS: Swap was successful.")
	else:
		print("FAILURE: Swap did not update rooms correctly.")

	frappe.db.commit()

if __name__ == "__main__":
	try:
		test_venue_booking_flow()
	except Exception as e:
		print(e)
		import traceback
		traceback.print_exc()
