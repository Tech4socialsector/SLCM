import frappe

def run():
    print("--- STEP 1: Link Target ---")
    field = frappe.get_meta("Time Table").get_field("instructor")
    if field:
        print(f"Options for instructor: {field.options}")
    else:
        print("instructor field not found!")
