import frappe

def check_program_fields():
    meta = frappe.get_meta("Program")
    for df in meta.fields:
        if df.fieldtype == "Table":
            print(f"Field: {df.fieldname}, Options: {df.options}")

if __name__ == "__main__":
    frappe.connect()
    check_program_fields()
    frappe.destroy()
