
import frappe
from frappe.utils import nowdate
from slcm.api.bulk_attendance import mark_attendance
import json

def reproduce():
    frappe.set_user("Administrator")
    
    # 1. Setup Data
    # terms
    if not frappe.db.exists("Academic Year", "2025-2026"):
        frappe.get_doc({"doctype": "Academic Year", "academic_year_name": "2025-2026", "year_start_date": "2025-01-01", "year_end_date": "2025-12-31"}).insert(ignore_permissions=True)
    
    # Term 1
    if not frappe.db.exists("Academic Term", "Term 1"):
        frappe.get_doc({"doctype": "Academic Term", "term_name": "Term 1", "academic_year": "2025-2026", "term_start_date": "2025-01-01", "term_end_date": "2025-06-30"}).insert(ignore_permissions=True)
    # Term 2
    if not frappe.db.exists("Academic Term", "Term 2"):
        frappe.get_doc({"doctype": "Academic Term", "term_name": "Term 2", "academic_year": "2025-2026", "term_start_date": "2025-07-01", "term_end_date": "2025-12-31"}).insert(ignore_permissions=True)

    # Program
    if not frappe.db.exists("Program", "Test Program"):
        frappe.get_doc({"doctype": "Program", "program_name": "Test Program", "program_abbreviation": "TP", "program_shortcode": "TP"}).insert(ignore_permissions=True)
    
    # Course
    course_name = "Test Course"
    existing_course = frappe.db.get_value("Course", {"course_name": course_name}, "name")
    if not existing_course:
        c = frappe.get_doc({"doctype": "Course", "name": course_name, "course_name": course_name, "course_code": "TC101"})
        c.insert(ignore_permissions=True)
        course = c.name
    else:
        course = existing_course

    # Faculty
    faculty = frappe.db.get_value("Faculty", {"first_name": "Test Faculty"}, "name")
    if not faculty:
        f = frappe.get_doc({"doctype": "Faculty", "first_name": "Test Faculty", "faculty_id": "TF001", "email": "tf@example.com", "designation": "Prof"})
        f.insert(ignore_permissions=True)
        faculty = f.name

    # Cohort 1 (Term 1)
    if not frappe.db.exists("Cohort", "Cohort T1"):
        frappe.get_doc({
            "doctype": "Cohort", "cohort_name": "Cohort T1", "cohort_code": "CT1", "program": "Test Program", 
            "academic_year": "2025-2026", "term_name": "Term 1", "start_date": "2025-01-01", "end_date": "2025-06-30"
        }).insert(ignore_permissions=True)
        
    # Cohort 2 (Term 2)
    if not frappe.db.exists("Cohort", "Cohort T2"):
        frappe.get_doc({
            "doctype": "Cohort", "cohort_name": "Cohort T2", "cohort_code": "CT2", "program": "Test Program", 
            "academic_year": "2025-2026", "term_name": "Term 2", "start_date": "2025-07-01", "end_date": "2025-12-31"
        }).insert(ignore_permissions=True)

    c_doc = frappe.get_doc("Course", course)
    original_course_name = c_doc.course_name
    
    # Enable multiple offerings by tweaking Course name temporarily
    # Course Offering 1 (Term 1)
    if not frappe.db.exists("Course Offering", "CO-Term1"):
        c_doc.course_name = "CO-Term1"
        c_doc.save()
        co = frappe.get_doc({
            "doctype": "Course Offering", "course_title": course, 
            "program": "Test Program", "cohort": "Cohort T1", "faculty": faculty, "status": "Open"
        })
        co.insert(ignore_permissions=True)
        co.submit()
        
    # Course Offering 2 (Term 2) - Created LATER/NEWER
    if not frappe.db.exists("Course Offering", "CO-Term2"):
        c_doc.course_name = "CO-Term2"
        c_doc.save()
        co = frappe.get_doc({
            "doctype": "Course Offering", "course_title": course, 
            "program": "Test Program", "cohort": "Cohort T2", "faculty": faculty, "status": "Open"
        })
        co.insert(ignore_permissions=True)
        co.submit()
    
    # Restore Course Name
    c_doc.course_name = original_course_name
    c_doc.save()

    # Student
    student = frappe.db.get_value("Student Master", {"first_name": "Test Student"}, "name")
    # (Assuming student exists from previous scripts, else create)

    # Office Hours Group linked to TERM 1
    oh_group_name = "Office Group Term 1"
    if not frappe.db.exists("Office Hours Group", oh_group_name):
        og = frappe.get_doc({
            "doctype": "Office Hours Group",
            "office_hours_group_name": oh_group_name,
            "program": "Test Program",
            "course": course, # Linked to Course
            "academic_year": "2025-2026",
            "academic_term": "Term 1", # Explicitly Term 1
            "students": [{"student": student, "active": 1, "total_office_hours": 0}]
        })
        og.insert(ignore_permissions=True)
    
    # CLEAR EXISTING for clean test
    frappe.db.delete("Student Attendance", {"office_hours_group": oh_group_name})
    
    # Mark Attendance using API
    print(f"Marking attendance for Group: {oh_group_name} (Term 1)...")
    mark_attendance(
        students_present=[{"student": student}],
        students_absent=[],
        date="2025-02-11",
        based_on="Office Hours",
        office_hours_group=oh_group_name
    )
    
    # Check generated Student Attendance
    att = frappe.db.get_value("Student Attendance", {"office_hours_group": oh_group_name}, ["name", "course_offer"], as_dict=True)
    if att:
        print(f"Created Attendance: {att.name}")
        print(f"Linked Course Offering: {att.course_offer}")
        
        if att.course_offer == "CO-Term1":
            print("SUCCESS: Linked to correct Term 1 Offering.")
        elif att.course_offer == "CO-Term2":
            print("FAILURE: Linked to WRONG Term 2 Offering (Newer one).")
        else:
            print(f"FAILURE: Linked to unexpected Offering: {att.course_offer}")
    else:
        print("FAILURE: Attendance not created.")

if __name__ == "__main__":
    try:
        reproduce()
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
