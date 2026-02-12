import frappe
from slcm.api.bulk_attendance import mark_attendance
from slcm.slcm.utils.attendance_calculator import calculate_student_attendance

def run():
    print("--- Starting Office Hours Calculation Verification ---")
    
    # Standard test data
    program = "BALLB(HONS)"
    date = "2026-02-12"
    student = "BALLB26001" 
    course = "Law of Crime"

    try:
        # 1. Mark Attendance (Office Hours)
        print(f"Marking attendance for {student} on {date} (Office Hours)...")
        
        # Get Academic Year from Course Offering for consistency
        offering_doc = frappe.db.get_value("Course Offering", {"program": program, "course_title": course}, ["name", "academic_year"], as_dict=True)
        academic_year = offering_doc.academic_year if offering_doc else "2025-2026"
        
        oh_group = frappe.db.get_value("Office Hours Group", {"program": program, "course": course}, "name")

        if not oh_group:
            print("No Office Hours Group found. Creating one for test...")
            doc = frappe.get_doc({
                "doctype": "Office Hours Group",
                "office_hours_group_name": "Test OH Group",
                "program": program,
                "course": course,
                "academic_year": academic_year,
            })
            doc.insert(ignore_permissions=True)
            oh_group = doc.name
            print(f"Created OH Group: {oh_group}")
        else:
            # Ensure existing group has academic year set for test
            frappe.db.set_value("Office Hours Group", oh_group, "academic_year", academic_year)
            print(f"Updated OH Group {oh_group} with academic_year {academic_year}")

        result = mark_attendance(
            students_present=[{"student": student}],
            students_absent=[],
            office_hours_group=oh_group,
            date=date,
            based_on="Office Hours"
        )
        print("Mark attendance result:", result)

        # 2. Verify Session Type of created record
        atts = frappe.get_all("Student Attendance", 
            filters={"student": student, "attendance_date": date, "session_type": "Office Hour"},
            fields=["name", "session_type", "course_offer", "hours_counted"]
        )
        
        if atts:
            print(f"SUCCESS: Found {len(atts)} Office Hour attendance records.")
            print(atts[0])
        else:
            print("FAILURE: No 'Office Hour' attendance record found.")
            atts_lecture = frappe.get_all("Student Attendance", 
                filters={"student": student, "attendance_date": date},
                fields=["name", "session_type"]
            )
            print("Actual records created:", atts_lecture)

        # 3. Verify Calculation
        # Find an offering to pass to calculator (context)
        offering = frappe.db.get_value("Course Offering", {"program": program, "course_title": course}, "name")
        if not offering:
            print("WARNING: No Course Offering found. Calculation test might be skipped or fail.")
        else:
            print(f"Calculating attendance for Offering: {offering}")
            summary = calculate_student_attendance(student, offering)
            print(f"Total Office Hours: {summary.get('total_office_hours')}")
            
            if summary.get('total_office_hours') > 0:
                print("SUCCESS: Office Hours Calculated!")
            else:
                print("FAILURE: Office Hours still 0.")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    frappe.db.rollback()
    print("Rolled back changes.")
