import frappe

def check_program_meta():
    meta = frappe.get_meta("Program")
    print(f"DocType: {meta.name}")
    print("Table Fields:")
    for field in meta.get_table_fields():
        print(f"  Fieldname: {field.fieldname}, Options: {field.options}")

if __name__ == "__main__":
    frappe.connect()
    check_program_meta()
    frappe.destroy()
