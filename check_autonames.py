import frappe

def get_autonames():
    print("Course autoname:", frappe.get_meta("Course").autoname)
    print("Course Offering autoname:", frappe.get_meta("Course Offering").autoname)
