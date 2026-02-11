
import frappe

def execute():
    states = [
        "Selected", "Pending REGO", "Pending FINO", "Pending Registration",
        "Pending Print & Scan", "Pending Residences", "Pending IT",
        "Final Verification REGO", "Draft", "Completed", "Re-Open"
    ]

    for state in states:
        if not frappe.db.exists("Workflow State", state):
            doc = frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "name": state})
            doc.insert(ignore_permissions=True)
            print(f"Created {state}")
    
    frappe.db.commit()
    print("Done")
