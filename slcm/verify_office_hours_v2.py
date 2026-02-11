
import frappe
from frappe.utils import today, add_days

def run():
    frappe.set_user("Administrator")
    
    # 1. Setup Data
    # Try to find an existing Enrolled Student
    print("Searching for existing enrolled student...")
    existing_enrollment = frappe.db.sql("""
        SELECT student, program, name as enrollment
        FROM `tabStudent Enrollment`
        WHERE status = 'Enrolled' AND docstatus < 2
        LIMIT 1
    """, as_dict=True)
    
    student = None
    program_name = None
    enrollment_doc = None
    
    if existing_enrollment:
        student_name = existing_enrollment[0].student
        program_name = existing_enrollment[0].program
        student = frappe.get_doc("Student Master", student_name)
        enrollment_doc = frappe.get_doc("Student Enrollment", existing_enrollment[0].enrollment)
        print(f"Found existing student: {student_name}, Program: {program_name}")
    else:
        print("No existing enrolled student found. Trying to find any student and enroll them.")
        # Find any student
        s_list = frappe.get_all("Student Master", limit=1)
        if s_list:
            student = frappe.get_doc("Student Master", s_list[0].name)
            student_name = student.name
            print(f"Found student: {student_name}")
        else:
            # Create minimal student with mandatory fields?
            # This is hard. Let's hope there is a student.
            print("No students found at all! Aborting.")
            return

        # Find any Program
        p_list = frappe.get_all("Program", limit=1)
        if p_list:
            program_name = p_list[0].name
            print(f"Found program: {program_name}")
        else:
            print("No program found! Aborting.")
            return
            
        # Try to enroll?
        # Check if already enrolled (ignoring status)
        if frappe.db.exists("Student Enrollment", {"student": student.name, "program": program_name}):
            print("Student already enrolled (maybe not Active/Enrolled status).")
        else:
             print("Attempting to enroll... (This might fail)")
             # ... simplified enrollment attempt ...

    # Find a course linked to this program or any course
    # If we found an enrollment, check its courses
    course_name = None
    if enrollment_doc and enrollment_doc.table_hxbo:
        course_name = enrollment_doc.table_hxbo[0].course
        print(f"Found course from enrollment: {course_name}")
    
    if not course_name:
        # Find any course
        c_list = frappe.get_all("Course", limit=1)
        if c_list:
            course_name = c_list[0].name
            print(f"Using arbitrary course: {course_name}")
        else:
             print("No course found!")
             return
            
    # 2. Test Office Hours Group Logic
    from slcm.slcm.doctype.office_hours_group.office_hours_group import get_students
    
    # Create Office Hours Group
    oh_group_name = "Test_OH_Group_001"
    if frappe.db.exists("Office Hours Group", oh_group_name):
        frappe.delete_doc("Office Hours Group", oh_group_name)
        
    oh_group = frappe.get_doc({
        "doctype": "Office Hours Group",
        "office_hours_group_name": oh_group_name,
        "program": program_name,
        "course": course_name
    }).insert()
    
    # Fetch Students
    fetched_students = get_students(program=program_name, course=course_name)
    print(f"Fetched Students: {len(fetched_students)}")
    
    found = False
    for s in fetched_students:
        if s.get("student") == student.name:
            found = True
            break
            
    if not found:
        print("ERROR: Verification Student not found in get_students result!")
        # Force add for testing next steps
        oh_group.append("students", {
            "student": student.name,
            "student_name": student_name,
            "active": 1
        })
    else:
        print("SUCCESS: Student found.")
        # Add to group
        for s in fetched_students:
             oh_group.append("students", {
                "student": s.get("student"),
                "student_name": s.get("student_name"),
                "active": s.get("active", 1)
            })
            
    oh_group.save()
    print("Office Hours Group saved with students.")
    
    # 3. Test Student Attendance Tool Logic
    from slcm.slcm.doctype.student_attendance_tool.student_attendance_tool import get_student_attendance_records
    
    tool_students = get_student_attendance_records(
        based_on="Office Hours",
        office_hours_group=oh_group.name,
        date=today()
    )
    
    print(f"Tool Fetched Students: {len(tool_students)}")
    if len(tool_students) > 0 and tool_students[0].get("student") == student.name:
        print("SUCCESS: Tool fetched correct student.")
    else:
        print("ERROR: Tool failed to fetch student.")
        
    # 4. Test Bulk Attendance Marking
    from slcm.api.bulk_attendance import mark_attendance
    
    # Mark Present
    result = mark_attendance(
        students_present=[{"student": student.name}],
        students_absent=[],
        based_on="Office Hours",
        office_hours_group=oh_group.name,
        date=today()
    )
    
    print("Mark Attendance Result:", result)
    
    # Verify Record
    att_name = frappe.db.exists("Student Attendance", {
        "student": student.name,
        "attendance_date": today(),
        "based_on": "Office Hours",
        "office_hours_group": oh_group.name,
        "status": "Present"
    })
    
    if att_name:
        print(f"SUCCESS: Student Attendance record created: {att_name}")
        att_doc = frappe.get_doc("Student Attendance", att_name)
        print(f"  Program: {att_doc.program}")
        print(f"  Course: {att_doc.course}")
    else:
        print("ERROR: Student Attendance record NOT found.")
        
    # Cleanup
    # frappe.delete_doc("Student Attendance", att_name)
    # frappe.delete_doc("Office Hours Group", oh_group_name)

if __name__ == "__main__":
    run()
