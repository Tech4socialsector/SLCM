
import frappe

def check_submittable():
    meta = frappe.get_meta("Student Attendance Condonation")
    print(f"Is Submittable: {meta.is_submittable}")
    
    # Also check if we can submit a non-submittable doc via script
    if not meta.is_submittable:
        try:
            doc = frappe.new_doc("Student Attendance Condonation")
            # Fill mandatory
            doc.student = frappe.get_all("Student Master", limit=1)[0].name
            doc.course_offering = frappe.get_all("Course Offering", limit=1)[0].name
            doc.number_of_hours = 1
            doc.number_of_sessions = 1
            doc.condonation_reason = "Medical reasons"
            doc.final_status = "Approved"
            doc.insert()
            print("Inserted Draft. Attempting Submit...")
            doc.submit()
            print("Submitted Successfully (Unexpected for non-submittable doc)")
        except Exception as e:
            print(f"Submit Failed as expected: {e}")

check_submittable()
