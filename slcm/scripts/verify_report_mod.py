import frappe
from slcm.slcm.utils.attendance_calculator import calculate_student_attendance
from slcm.slcm.report.comprehensive_attendance_report.comprehensive_attendance_report import execute as execute_report

def run_verification():
    print("Starting verification...")
    
    # 1. Get a test student
    student = frappe.get_all("Student Master", limit=1)
    if not student:
        print("No student found. Please create a student first.")
        return
    student_id = student[0].name
    print(f"Using Student: {student_id}")
    
    # 2. Get a course offering
    offering = frappe.get_all("Course Offering", limit=1)
    if not offering:
        print("No Course Offering found.")
        return
    offering_id = offering[0].name
    print(f"Using Course Offering: {offering_id}")
    
    # 3. Calculate Attendance (This should populate new fields)
    print("Calculating attendance...")
    summary_data = calculate_student_attendance(student_id, offering_id)
    
    # 4. Verify fields in summary
    summary_doc = frappe.get_doc("Attendance Summary", {"student": student_id, "course_offering": offering_id})
    print(f"Summary Fields (DB):")
    print(f"  Total Classes: {summary_doc.total_classes}")
    print(f"  Attended Classes (Total): {summary_doc.attended_classes}")
    print(f"  Raw Attended Classes: {summary_doc.raw_attended_classes}")
    print(f"  Office Hours Attended: {summary_doc.office_hours_attended}")
    
    if summary_doc.raw_attended_classes is None:
        print("ERROR: raw_attended_classes is None!")
    else:
        print("SUCCESS: raw_attended_classes populated.")
        
    # 5. Run Report
    print("Running Report...")
    filters = {"student": student_id, "course": summary_doc.course}
    columns, data = execute_report(filters)
    
    # Find the row for this student
    row = next((r for r in data if r['student'] == student_id and r['course'] == summary_doc.course), None)
    
    if row:
        print("Report Row Data:")
        print(f"  Class Attended: {row.get('raw_attended_classes')}")
        print(f"  Office Hours Attended: {row.get('office_hours_attended')}")
        print(f"  Total Hours Calculated: {row.get('total_hours_attended_calc')}")
        print(f"  Is Condonation Applied: {row.get('is_condonation_applied')}")
        print(f"  Condonation Hours: {row.get('condonation_hours')}")
        print(f"  % Before Condonation: {row.get('percentage_before_condonation')}")
        print(f"  % After Condonation: {row.get('percentage_after_condonation')}")
    else:
        print("Row not found in report data.")

if __name__ == "__main__":
    run_verification()
