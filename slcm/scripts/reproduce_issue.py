
import frappe
from frappe.utils import today, add_days, add_months

def create_data():
    frappe.db.rollback()
    
    # Reload the DocType to apply the autoname change
    frappe.reload_doc("slcm", "doctype", "student_attendance_condonation")

    # 1. Find or Create Student
    student_id = None
    existing_students = frappe.get_all("Student Master", limit=1)
    if existing_students:
        student_id = existing_students[0].name
        print(f"Using existing Student: {student_id}")
    else:
        print("No existing student found. Cannot proceed without mandatory fields.")
        return

    # 2. Create Dependencies (Department, Faculty, Program, Cohort)

    # Department
    department_name = "Department of Law"
    if not frappe.db.exists("Department", department_name):
        frappe.get_doc({
            "doctype": "Department",
            "department_id": "DEPT-LAW",
            "department_name": department_name,
            "status": "Active"
        }).insert(ignore_permissions=True)
    
    # Faculty
    faculty_name = "TEST-FACULTY-1"
    if not frappe.db.exists("Faculty", {"first_name": "Test", "last_name": "Faculty"}):
         f = frappe.get_doc({
             "doctype": "Faculty",
             "faculty_id": "TF001",
             "first_name": "Test",
             "last_name": "Faculty",
             "email": "test.faculty@example.com",
             "designation": "Professor",
             "department": department_name,
             "status": "Active"
         })
         f.insert(ignore_permissions=True)
         faculty_name = f.name
    else:
         faculty_name = frappe.db.get_value("Faculty", {"first_name": "Test", "last_name": "Faculty"}, "name")

    # Program
    program_name = "TEST-PROGRAM"
    if not frappe.db.exists("Program", program_name):
        frappe.get_doc({
            "doctype": "Program",
            "program_name": program_name,
            "program_shortcode": "TP",
            "program_status": "Active",
            "department": department_name
        }).insert(ignore_permissions=True)
    
    # We need an Academic Year and Term
    academic_year = frappe.db.get_value("Academic Year", {}, "name")
    if not academic_year:
         academic_year = "2025-2026"
         if not frappe.db.exists("Academic Year", academic_year):
            frappe.get_doc({"doctype": "Academic Year", "year_name": academic_year}).insert(ignore_permissions=True)

    term_name = frappe.db.get_value("Academic Term", {"academic_year": academic_year}, "name")
    if not term_name:
         term_name = "Term 1"
         if not frappe.db.exists("Academic Term", {"term_name": term_name, "academic_year": academic_year}):
            frappe.get_doc({
                "doctype": "Academic Term", 
                "term_name": term_name, 
                "academic_year": academic_year,
                "term_start_date": today(),
                "term_end_date": add_months(today(), 6)
            }).insert(ignore_permissions=True)

    # Cohort
    cohort_name = "TEST-COHORT"
    if not frappe.db.exists("Cohort", cohort_name):
        frappe.get_doc({
            "doctype": "Cohort",
            "cohort_name": cohort_name,
            "cohort_code": "TC-2025",
            "program": program_name,
            "academic_year": academic_year,
            "term_name": term_name,
            "start_date": today(),
            "end_date": add_months(today(), 6),
            "status": "Active"
        }).insert(ignore_permissions=True)


    # 3. Create Course Master, Course & Course Offering
    course_name = "TEST-COURSE-CONDONATION"
    
    # Create the Master first
    if not frappe.db.exists("Course Master", course_name):
        # Course Master uses "prompt" naming
        cm = frappe.get_doc({
            "doctype": "Course Master",
            "name": course_name
        })
        cm.name = course_name 
        cm.insert(ignore_permissions=True)

    # Create the Course
    if not frappe.db.exists("Course", course_name):
        frappe.get_doc({
            "doctype": "Course",
            "course_code": "TC-COND",
            "course_name": course_name, # Link to Course Master
            "description": "Test Course",
            "department": department_name
        }).insert(ignore_permissions=True)

    offering_id = "TEST-OFFERING-CONDONATION"
    if not frappe.db.exists("Course Offering", {"course_title": course_name}):
        offering = frappe.get_doc({
            "doctype": "Course Offering",
            "course_title": course_name,
            "program": program_name,
            "cohort": cohort_name,
            "academic_year": academic_year,
            "term_name": term_name,
            "faculty": faculty_name,
            "status": "Open"
        }).insert(ignore_permissions=True)
        offering_id = offering.name
    else:
        offering_id = frappe.db.get_value("Course Offering", {"course_title": course_name}, "name")

    print(f"Student: {student_id}")
    print(f"Offering: {offering_id}")

    # 4. Create Attendance Sessions (One Conducted, One Absent for Student)
    # Session 1
    session1 = frappe.get_doc({
        "doctype": "Attendance Session",
        "course_offering": offering_id,
        "session_type": "Lecture",
        "session_date": today(),
        "session_start_time": "10:00:00",
        "session_end_time": "11:00:00",
        "duration_hours": 1.0,
        "session_status": "Conducted"
    }).insert(ignore_permissions=True)

    # Mark Absent
    frappe.get_doc({
        "doctype": "Student Attendance",
        "student": student_id,
        "course_offer": offering_id,
        "attendance_date": today(),
        "date": today(), # Both date fields seem required
        "session_type": "Lecture",
        "status": "Absent",
        "attendance_session": session1.name,
        "hours_counted": 1.0
    }).insert(ignore_permissions=True)

    # Calculate initial summary using the function directly to be sure
    from slcm.slcm.utils.attendance_calculator import calculate_student_attendance
    summary_before = calculate_student_attendance(student_id, offering_id)
    print(f"Summary Before Condonation: {summary_before['attended_classes']} / {summary_before['total_classes']} ({summary_before['attendance_percentage']}%)")
    
    # 5. Create Condonation
    # Force clean up existing condonation if any for this test
    # frappe.db.sql("DELETE FROM `tabStudent Attendance Condonation` WHERE student=%s AND course_offering=%s", (student_id, offering_id))

    condonation = frappe.get_doc({
        "doctype": "Student Attendance Condonation",
        "student": student_id,
        "student_name": summary_before.get('student_name', 'Test Student'),
        "course_offering": offering_id,
        "number_of_sessions": 1,
        "number_of_hours": 1.0,
        "condonation_reason": "Medical reasons",
        "final_status": "Approved"
    })
    condonation.insert(ignore_permissions=True)
    condonation.submit()
    
    print(f"Condonation Created: {condonation.name} (Approved, 1 hour)")

    # 6. Check Summary After - Validating Automatic Trigger
    summary_doc_name = frappe.db.exists("Attendance Summary", {"student": student_id, "course_offering": offering_id})
    summary_after = frappe.get_doc("Attendance Summary", summary_doc_name)
    
    print(f"Summary After Condonation (Automatic): {summary_after.attended_classes} / {summary_after.total_classes} ({summary_after.attendance_percentage}%)")

    # In our scenario:
    # Total Classes (Hours) = 1.0
    # Attended (before) = 0.0 (Absent)
    # Condonation = 1.0 Hour
    # Expected Attended (after) = 0.0 + 1.0 = 1.0
    # Expected % = 100%

    if summary_after.attended_classes > summary_before['attended_classes']:
        print("SUCCESS: Condonation added to attendance automatically.")
    else:
        print("FAILURE: Condonation NOT added to attendance automatically.")
        
    frappe.db.rollback() # Rollback to keep DB clean

