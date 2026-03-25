import frappe
from slcm.slcm.utils.attendance_calculator import calculate_office_hours

student = "BALLB26001"
course_offering = "Law of Crime"

print(f"Testing calculation for {student} in {course_offering}")

# Manual check of the values
offering = frappe.db.get_value("Course Offering", course_offering, ["course_title", "academic_year"], as_dict=True)
print(f"Offering Details: {offering}")

# Run function
result = calculate_office_hours(student, course_offering)
print(f"Result: {result}")

# Run SQL manually to see raw output
sql = """
    SELECT 
        name, hours_counted, course_offer, course, academic_year
    FROM `tabStudent Attendance`
    WHERE student = %s
    AND (
        course_offer = %s
        OR (
            course_offer IS NULL 
            AND course = %s 
            AND academic_year = %s
        )
    )
    AND session_type = 'Office Hour'
    AND status IN ('Present', 'Late', 'Excused')
    AND docstatus < 2
"""

data = frappe.db.sql(sql, (student, course_offering, offering.course_title, offering.academic_year), as_dict=True)
print(f"Manual SQL Rows: {data}")
