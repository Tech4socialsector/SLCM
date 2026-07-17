import frappe

def execute():
    meta = frappe.get_meta("PACE Application")
    for field in meta.fields:
        print(field.fieldname, field.fieldtype, field.label)
