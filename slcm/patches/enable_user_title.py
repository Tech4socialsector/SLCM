import frappe

def execute():
    frappe.reload_doc("core", "doctype", "user")
    frappe.db.set_value("DocType", "User", "show_title_field_in_link", 1)
    frappe.db.set_value("DocType", "User", "title_field", "full_name")
    frappe.db.commit()
