import frappe

def print_student_enrollment():
    if frappe.db.exists("DocType", "Student Enrollment"):
        print([f.fieldname for f in frappe.get_meta("Student Enrollment").fields])

if __name__ == "__main__":
    print_student_enrollment()
