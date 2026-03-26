import frappe
import sys

def reproduce():
    print("Creating minimal Class Schedule...")
    term = frappe.db.get_value("Term Configuration", {}, "name")
    course = frappe.db.get_value("Course", {}, "name")
    
    # We need a venue.
    venue = frappe.db.get_value("Venue Booking", {"status": "Approved"}, "name")
    if not venue:
        print("No Approved Venue found, using any venue or failing.")
        venue = frappe.db.get_value("Venue Booking", {}, "name")

    if not term or not course or not venue:
        print("Missing dependencies.")
        return

    print(f"Using Term={term}, Course={course}, Venue={venue}")

    # Try 1: Without status (should depend on fetch or default)
    try:
        doc = frappe.get_doc({
            "doctype": "Class Schedule",
            "term": term,
            "course": course,
            "venue": venue,
            "schedule_date": "2026-02-15",
            "from_time": "12:00:00",
            "to_time": "13:00:00",
            # No status
        })
        doc.insert()
        print("Success without status.")
    except Exception as e:
        print(f"!!! Error without status: {e}")

    # Try 2: With status='Approved'
    try:
        doc2 = frappe.get_doc({
            "doctype": "Class Schedule",
            "term": term,
            "course": course,
            "venue": venue,
            "schedule_date": "2026-02-15",
            "from_time": "13:00:00",
            "to_time": "14:00:00",
            "status": "Approved"
        })
        doc2.insert()
        print("Success WITH status='Approved'.")
    except Exception as e:
        print(f"!!! Error WITH status='Approved': {e}")

reproduce()
