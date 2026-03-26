import frappe

def check():
    print("Checking Class Schedule Fields...")
    meta = frappe.get_meta("Class Schedule")
    found = False
    for field in meta.fields:
        if field.label == "Current Status" or field.fieldname == "current_status":
            print(f"FOUND in Meta: {field.fieldname}, Type: {field.fieldtype}, Label: {field.label}")
            found = True
            
    print("Checking Property Setters...")
    ps = frappe.get_all("Property Setter", filters={"doc_type": "Class Schedule", "property": "label"}, fields=["field_name", "value"])
    for p in ps:
        if p.value == "Current Status":
             print(f"FOUND in Property Setter: Field {p.field_name} renamed to {p.value}")
             found = True

    print("Checking Custom Fields...")
    cf = frappe.get_all("Custom Field", filters={"dt": "Class Schedule"}, fields=["fieldname", "label", "fieldtype"])
    for c in cf:
        if c.label == "Current Status":
             print(f"FOUND in Custom Field: {c.fieldname}, Type: {c.fieldtype}")
             found = True

    if not found:
        print(" 'Current Status' label NOT found in Class Schedule.")

    print("\nChecking Attendance Session...")
    meta_as = frappe.get_meta("Attendance Session")
    for field in meta_as.fields:
        if field.label == "Current Status":
            print(f"Found in Attendance Session: {field.fieldname}")

check()
