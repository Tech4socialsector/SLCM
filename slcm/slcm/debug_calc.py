import frappe
from slcm.slcm.utils.attendance_calculator import calculate_office_hours

def run():
    student = "BALLB26001"
    course_offering = "Law of Crime"

    print(f"Testing calculation for {student} in {course_offering}")

    try:
        # 1. Get Context
        offering = frappe.db.get_value("Course Offering", course_offering, ["course_title", "academic_year"], as_dict=True)
        if not offering:
            print(f"Course Offering {course_offering} not found!")
            return

        print(f"Offering Context -> Course: {offering.course_title}, Year: {offering.academic_year}")

        # 2. Run Calculator Function
        result = calculate_office_hours(student, course_offering)
        print(f"Calculator Result: {result}")

        # 3. Run Manual SQL to debug matches
        sql = """
            SELECT 
                name, hours_counted, course_offer, course, academic_year, status, docstatus, session_type
            FROM `tabStudent Attendance`
            WHERE student = %s
        """
        all_recs = frappe.db.sql(sql, (student,), as_dict=True)
        print("--- All Attendance Records for Student ---")
        for r in all_recs:
            print(r)

        # 4. targeted SQL
        targeted_sql = """
            SELECT 
                COALESCE(SUM(hours_counted), 0) as total_hours
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
        match_val = frappe.db.sql(targeted_sql, (student, course_offering, offering.course_title, offering.academic_year))
        print(f"Direct SQL Match Value: {match_val}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
