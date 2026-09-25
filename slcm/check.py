import frappe

def run():
    print("--- Error Logs ---")
    logs = frappe.get_all("Error Log", fields=["name", "creation", "method", "error"], order_by="creation desc", limit=5)
    for log in logs:
        print(f"{log.creation} | {log.method}")
        print(log.error)
        print("-" * 40)
        
    print("\n--- Faculty DocType Check ---")
    if frappe.db.exists("DocType", "Faculty"):
        meta = frappe.get_meta("Faculty")
        fields = [f.fieldname for f in meta.fields]
        print("Faculty exists. Fields:")
        print(fields)
    else:
        print("DocType Faculty does NOT exist!")
