import frappe
import sys

def reproduce():
    print("Fetching dependencies for FULL repro...")
    term = frappe.db.get_value("Term Configuration", {}, "name")
    course = frappe.db.get_value("Course", {}, "name")
    venue = frappe.db.get_value("Venue Booking", {"status": "Approved"}, "name")
    
    # Optional fields present in user request
    class_config = frappe.db.get_value("Class Configuration", {}, "name")
    instructor = frappe.db.get_value("Faculty", {}, "name")
    course_offering = frappe.db.get_value("Course Offering", {}, "name") # Assuming one exists
    student_group = frappe.db.get_value("Student Group", {}, "name")
    # Section? usually fetched or part of group
    
    print(f"Dependencies: Term={term}, Course={course}, Venue={venue}")
    print(f"Optionals: Config={class_config}, Instr={instructor}, Off={course_offering}, Group={student_group}")

    doc_data = {
        "doctype": "Class Schedule",
        "term": term,
        "course": course,
        "venue": venue,
        "schedule_date": "2026-02-15",
        "from_time": "14:00:00",
        "to_time": "15:00:00",
        "status": "Approved"
    }

    if class_config: doc_data["class_configuration"] = class_config
    if instructor: doc_data["instructor"] = instructor
    if course_offering: doc_data["course_offering"] = course_offering
    if student_group: doc_data["student_group"] = student_group

    print("Inserting Class Schedule with FULL data...")
    try:
        doc = frappe.get_doc(doc_data)
        doc.insert()
        print("Success.")
    except Exception as e:
        print(f"!!! CAUGHT EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

reproduce()
