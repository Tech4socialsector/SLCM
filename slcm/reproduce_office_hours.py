
import frappe
from frappe.utils import nowdate, now

def reproduce():
    frappe.set_user("Administrator")
    
    # 1. Setup Data
    # Ensure dependencies exist
    if not frappe.db.exists("Program", "Test Program"):
        frappe.get_doc({"doctype": "Program", "program_name": "Test Program", "program_abbreviation": "TP", "program_shortcode": "TP"}).insert(ignore_permissions=True)
    
    course_name = "Test Course"
    
    existing_course = frappe.db.get_value("Course", {"course_name": course_name}, "name")
    if existing_course:
        course = existing_course
    else:
        c = frappe.get_doc({"doctype": "Course", "name": course_name, "course_name": course_name, "course_code": "TC101"})
        c.insert(ignore_permissions=True)
        course = c.name

    if not frappe.db.exists("Academic Year", "2025-2026"):
        frappe.get_doc({
            "doctype": "Academic Year", 
            "academic_year_name": "2025-2026",
            "year_start_date": "2025-01-01",
            "year_end_date": "2025-12-31"
        }).insert(ignore_permissions=True)
        
    if not frappe.db.exists("Academic Term", "Term 1"):
        frappe.get_doc({
            "doctype": "Academic Term",
            "term_name": "Term 1", 
            "academic_year": "2025-2026",
            "term_start_date": "2025-01-01",
            "term_end_date": "2025-06-30"
        }).insert(ignore_permissions=True)

    
    if not frappe.db.exists("Cohort", "Test Cohort"):
        frappe.get_doc({
            "doctype": "Cohort",
            "cohort_name": "Test Cohort", 
            "cohort_code": "TC2025",
            "program": "Test Program",
            "start_year": "2025",
            "end_year": "2029",
            "academic_year": "2025-2026",
            "term_name": "Term 1",
            "start_date": "2025-01-01",
            "end_date": "2025-06-30"
        }).insert(ignore_permissions=True)

    
    faculty = frappe.db.get_value("Faculty", {"first_name": "Test Faculty"}, "name")
    if not faculty:
        f = frappe.get_doc({
            "doctype": "Faculty",
            "first_name": "Test Faculty",
            "faculty_id": "TF001",
            "email": "test_faculty@example.com",
            "designation": "Professor"
        })
        f.insert(ignore_permissions=True)
        faculty = f.name
        print(f"Created Faculty: {faculty}")

    # Ensure Course Offering
    course_offering = frappe.db.get_value("Course Offering", {"course_title": course, "docstatus": 1}, "name")
    if not course_offering:
        print("Creating new Course Offering linked to valid Course...")
        offering = frappe.get_doc({
            "doctype": "Course Offering",
            "program": "Test Program",
            "course_title": course, # Use ID here
            "course_name": "Test Course 101 Valid", # Different name to avoid collision
            "cohort": "Test Cohort",
            "faculty": faculty,
            "status": "Open",
            "academic_year": "2025-2026", # Added because they are mandatory but hidden/fetched sometimes? 
            "term_name": "Term 1"         # Added just in case
        })
        offering.insert(ignore_permissions=True)
        offering.submit() # Course Offering must be submitted to be valid usually
        course_offering = offering.name
        print(f"Created Course Offering: {course_offering}")
    
    # Ensure Student
    student = frappe.db.get_value("Student Master", {"first_name": "Test Student"}, "name")
    if not student:
        s = frappe.get_doc({
            "doctype": "Student Master",
            "first_name": "Test Student",
            "email": "test_student@example.com",
            # Mandatory fields
            "application_number": "APP001",
            "dob": "2000-01-01",
            "gender": "Male",
            "marital_status": "Unmarried",
            "nationality": "Indian",
            "personal_email": "test_student_personal@example.com",
            "phone": "+91-9999999999",
            # Class X
            "class_x_completion_year": "2016",
            "class_x_percentage": 90.0,
            "class_x_school": "Test School X",
            "class_x_board": "CBSE",
            # Class XII
            "class_xii_exam_name": "Class XII",
            "class_xii_completion_year": "2018",
            "class_xii_school": "Test School XII",
            "class_xii_board": "CBSE",
            "class_xii_percentage": 90.0,
            # UG (if mandatory? JSON says ug_degree_completed is in field_order but reqd? Let's check JSON... line 118... reqd not set. But error said 'ug_degree_completed'?)
            # Wait, the error message listed 'ug_degree_completed' as missing?
            # Error: ... ug_degree_completed, aadhaar_card, pan_card, passport_size_photo, std_x_marksheet, class_xii_marksheet
            
            # Documents (Attach Image/File fields - we can pass dummy strings or skip if not strictly validated as file existence)
            # "ug_degree_completed": "No", # Check if it's a Check or Select?
            # Error listed it. Let's look at JSON for ug_degree_completed.
        })
        # Add missing fields based on my reading of JSON/Error
        s.ug_degree_completed = "No" # Or 0 if Check
        
        # Files (Attach Image/File) - mandatory?
        # Error listed: aadhaar_card, pan_card, passport_size_photo, std_x_marksheet, class_xii_marksheet
        # I'll provide dummy URLs
        s.aadhaar_card = "/files/dummy.pdf"
        s.pan_card = "/files/dummy.pdf"
        s.passport_size_photo = "/files/dummy.jpg"
        s.std_x_marksheet = "/files/dummy.pdf"
        s.class_xii_marksheet = "/files/dummy.pdf"

        s.insert(ignore_permissions=True)
        student = s.name
        print(f"Created Student: {student}")

    offering_doc = frappe.get_doc("Course Offering", course_offering)
    print(f"DEBUG: offering_doc.course_title = {offering_doc.course_title}")
    
    real_course_name = frappe.db.get_value("Course", {"course_name": "Test Course"}, "name")
    print(f"DEBUG: Real Course with course_name 'Test Course' has name: {real_course_name}")
    print(f"DEBUG: Does Course 'Test Course' exist by name? {frappe.db.exists('Course', 'Test Course')}")

    print(f"Using Course Offering: {course_offering}")
    print(f"Using Student: {student}")
    
    # Create Office Hours Group if not exists
    oh_group_name = f"Test Office Group - {offering_doc.course_title}"
    oh_group_exists = frappe.db.exists("Office Hours Group", {"office_hours_group_name": oh_group_name})
    
    if not oh_group_exists:
        # try:
        oh_group = frappe.get_doc({
            "doctype": "Office Hours Group",
            "office_hours_group_name": oh_group_name,
            "program": offering_doc.program,
            "course": offering_doc.course_title,
            "academic_year": offering_doc.academic_year,
            "academic_term": offering_doc.term_name,
            "students": [{
                "student": student,
                "active": 1,
                "total_office_hours": 0
            }]
        })
        oh_group.insert(ignore_permissions=True)
        print(f"Created Office Hours Group: {oh_group.name}")
        # except Exception as e:
        #     print(f"Failed to create Office Hours Group: {e}")
        #     return
    else:
        oh_group = frappe.get_doc("Office Hours Group", oh_group_exists)
        # Ensure student is in it
        found = False
        for row in oh_group.students:
            if row.student == student:
                found = True
                break
        if not found:
            oh_group.append("students", {"student": student, "active": 1})
            oh_group.save(ignore_permissions=True)
        print(f"Using Existing Office Hours Group: {oh_group.name}")

    # Clear existing office hours attendance for this test
    frappe.db.delete("Student Attendance", {
        "student": student,
        "course_offer": course_offering,
        "session_type": "Office Hour"
    })
    
    # Reset total in group
    row_name = frappe.db.get_value("Student Group Student", {"parent": oh_group.name, "student": student}, "name")
    frappe.db.set_value("Student Group Student", row_name, "total_office_hours", 0)

    # 2. Mark Attendance (Office Hour)
    # Create an Attendance Session manually or just create Student Attendance records (Manual source)
    print("Marking Office Hour Attendance...")
    
    attendance = frappe.get_doc({
        "doctype": "Student Attendance",
        "student": student,
        "attendance_date": nowdate(),
        "date": nowdate(),
        "status": "Present",
        "based_on": "Office Hours",
        "office_hours_group": oh_group.name,
        "course_offer": course_offering,
        "session_type": "Office Hour",
        "hours_counted": 2.0,
        "source": "Manual"
    })
    attendance.insert(ignore_permissions=True)
    
    # 3. Trigger Calculation
    # calculate_student_attendance is called?. 
    # Usually triggered by hook on Student Attendance save? 
    # Or explicitly called. Based on `attendance_session.py`, it's called on submit.
    # But Student Attendance is usually just inserted. 
    # Let's call the calculation function explicitly to verify the logic.
    
    from slcm.slcm.utils.attendance_calculator import calculate_student_attendance
    print("Triggering Calculation...")
    calculate_student_attendance(student, course_offering)
    
    # 4. Verify
    print("Verifying Results...")
    
    # Check Summary
    summary = frappe.db.get_value("Attendance Summary", 
        {"student": student, "course_offering": course_offering}, 
        "total_office_hours"
    )
    print(f"Attendance Summary Office Hours: {summary}")
    
    # Check Student Group Student
    group_hours = frappe.db.get_value("Student Group Student", row_name, "total_office_hours")
    print(f"Student Group Student Office Hours: {group_hours}")
    
    if float(group_hours or 0) == 2.0:
        print("SUCCESS: Office Hours updated correctly in child table.")
    else:
        print("FAILURE: Office Hours NOT updated correctly.")

if __name__ == "__main__":
    try:
        reproduce()
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
