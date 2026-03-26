import frappe

def inspect():
    print("Inspecting Class Schedule Link Fields...")
    meta = frappe.get_meta("Class Schedule")
    link_fields = meta.get_link_fields()
    
    found = False
    for df in link_fields:
        print(f"Field: {df.fieldname}, Label: {df.label}, Options: {df.options}")
        if df.label == "Current Status" or df.options == "Current Status":
             print("!!! FOUND CULPRIT !!!")
             found = True
             
    if not found:
        print("No Link Field with label or options 'Current Status' found via meta.")

    # Check for Dynamic Links
    print("\nDynamic Links:")
    dyn_links = meta.get_dynamic_link_fields()
    for df in dyn_links:
        print(f"Field: {df.fieldname}, Options: {df.options}")

inspect()
