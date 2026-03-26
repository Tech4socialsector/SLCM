import frappe
import sys

def reproduce():
    print("Fetching dependencies...")
    term = frappe.db.get_value("Term Configuration", {}, "name")
    if not term:
        print("No Term Configuration found.")
        return

    course = frappe.db.get_value("Course", {}, "name")
    if not course:
        print("No Course found.")
        return

    # Use existing Venue Booking or find one
    venue = frappe.db.get_value("Venue Booking", {"status": "Approved"}, "name")
    if not venue:
        # Create one
        room = frappe.db.get_value("Room", {}, "name")
        if not room:
            print("No Room found.")
            return
        
        vb = frappe.get_doc({
            "doctype": "Venue Booking",
            "room": room,
            "venue_type": "Classroom",
            "start_datetime": "2026-02-14 10:00:00",
            "end_datetime": "2026-02-14 11:00:00",
            "reason": "Test Repro",
            "status": "Approved"
        })
        vb.insert()
        venue = vb.name
        print(f"Created Venue Booking: {venue}")

    print(f"Dependencies: Term={term}, Course={course}, Venue={venue}")

    try:
        doc = frappe.get_doc({
            "doctype": "Class Schedule",
            "term": term,
            "course": course,
            "venue": venue,
            "schedule_date": "2026-02-14",
            "from_time": "10:00:00",
            "to_time": "11:00:00",
            "status": "Approved" # Fetched from Venue, but let's set it explicitly if possible (it's Read Only usually)
        })
        # Note: 'status' is Read Only in JSON, so setting it in get_doc might be ignored during insert unless we force it or it fetches.
        # But if it fetches from Venue, and Venue is Approved, it becomes Approved.
        
        print("Saving Class Schedule...")
        sys.stdout.flush()
        doc.insert()
        print("Success.")
    except Exception as e:
        print(f"!!! CAUGHT EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

reproduce()
