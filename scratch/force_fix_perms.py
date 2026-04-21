
import frappe

def run():
    doctype = "PACE Document Verification"
    roles_to_add = ["PACE Admission Manager", "Admission Admin", "Academic Manager"]
    
    for role in roles_to_add:
        if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role}):
            print(f"Adding Custom DocPerm for {role} on {doctype}")
            frappe.get_doc({
                "doctype": "Custom DocPerm",
                "parent": doctype,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role,
                "read": 1,
                "write": 1,
                "create": 1,
                "delete": 1,
                "export": 1,
                "print": 1,
                "report": 1,
                "share": 1,
                "permlevel": 0
            }).insert(ignore_permissions=True)
        else:
            print(f"Custom DocPerm for {role} already exists.")
            # Ensure read/write is enabled
            frappe.db.set_value("Custom DocPerm", {"parent": doctype, "role": role}, {
                "read": 1,
                "write": 1,
                "create": 1,
                "delete": 1
            })
            
    frappe.db.commit()
    frappe.clear_cache(doctype=doctype)
    print("Permissions fixed and cache cleared.")

if __name__ == "__main__":
    run()
