import frappe

def inspect():
    meta = frappe.get_meta("Class Schedule")
    print(f"Inspecting 'status' field in Class Schedule...")
    field = meta.get_field("status")
    if field:
        print(f"Field Found: {field.fieldname}")
        print(f"Type: {field.fieldtype}")
        print(f"Options: {field.options}")
        print(f"Label: {field.label}")
        print(f"Fetch From: {field.fetch_from}")
    else:
        print("Field 'status' NOT found in Meta.")

    print("\nCheck for ANY field with options='Current Status' or label='Current Status'")
    for f in meta.fields:
        if f.options == "Current Status" or f.label == "Current Status" or f.label == "Selected":
            print(f"!!! MATCH !!! Field: {f.fieldname}, Label: {f.label}, Options: {f.options}")

inspect()
