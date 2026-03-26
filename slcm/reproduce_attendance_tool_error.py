
import frappe
from frappe.utils import nowdate
from slcm.api.bulk_attendance import mark_attendance
import json

def reproduce():
    frappe.set_user("Administrator")
    
    # Setup Data (Reuse logic from previous script or assume exist if run previously)
    # But for robustness, let's ensure minimal required data.
    
    # 1. Course
    course_name = "Test Course"
    existing_course = frappe.db.get_value("Course", {"course_name": course_name}, "name")
    if not existing_course:
        try:
            c = frappe.get_doc({"doctype": "Course", "name": course_name, "course_name": course_name, "course_code": "TC101"})
            c.insert(ignore_permissions=True)
            course = c.name
        except frappe.DuplicateEntryError:
             course = frappe.db.get_value("Course", {"course_name": course_name}, "name")
    else:
        course = existing_course
        
    # 2. Student
    student_name = "Test Student"
    student = frappe.db.get_value("Student Master", {"first_name": student_name}, "name")
    if not student:
        # Create minimal student if not exists (assume previous script ran effectively or adapt logic)
        # Using previous script logic here for safety
         s = frappe.get_doc({
            "doctype": "Student Master",
            "first_name": "Test Student",
            "email": "test_student@example.com",
            "application_number": "APP001-TOOL", # Unique
            "dob": "2000-01-01",
            "gender": "Male",
            "marital_status": "Unmarried",
            "nationality": "Indian",
            "personal_email": "test_student_personal_tool@example.com",
            "phone": "+91-9999999999",
            # Dummy mandatory fields
             "class_x_completion_year": "2016",
             "class_x_percentage": 90.0,
             "class_x_school": "Test School X",
             "class_x_board": "CBSE",
             "class_xii_exam_name": "Class XII",
             "class_xii_completion_year": "2018",
             "class_xii_school": "Test School XII",
             "class_xii_board": "CBSE",
             "class_xii_percentage": 90.0,
        })
         s.ug_degree_completed = "No"
         s.aadhaar_card = "/files/dummy.pdf"
         s.pan_card = "/files/dummy.pdf"
         s.passport_size_photo = "/files/dummy.jpg"
         s.std_x_marksheet = "/files/dummy.pdf"
         s.class_xii_marksheet = "/files/dummy.pdf"
         s.insert(ignore_permissions=True)
         student = s.name

    # 3. Office Hours Group
    # Find active OH Group
    oh_group = frappe.db.get_value("Office Hours Group", {"office_hours_group_name": ["like", "Test Office Group%"]}, "name")
    if not oh_group:
        print("SKIP: Office Hours Group not found. Please run reproduce_office_hours.py first to setup data.")
        return

    print(f"Testing with Student: {student}, Group: {oh_group}")

    # 4. Call API
    print("Calling mark_attendance with based_on='Office Hours'...")
    try:
        result = mark_attendance(
            students_present=[{"student": student}],
            students_absent=[],
            date=nowdate(),
            based_on="Office Hours",
            office_hours_group=oh_group
        )
        print("API Call Result:", result)
        if result.get("status") == "success":
            print("SUCCESS: Attendance marked via Tool API.")
        else:
            print("FAILURE: API returned non-success status.")
            
    except Exception as e:
        print(f"FAILURE: API Call raised exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        reproduce()
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        print(f"Error: {e}")
