import frappe
import json
import os

def execute():
    # Define the states from student_master_workflow.json
    states = [
        "Selected",
        "Pending REGO",
        "Pending FINO",
        "Pending Registration",
        "Pending Print & Scan",
        "Pending Residences",
        "Pending IT",
        "Final Verification REGO",
        "Draft",
        "Completed",
        "Re-Open"
    ]

    for state_name in states:
        if not frappe.db.exists("Workflow State", state_name):
            print(f"Creating Workflow State: {state_name}")
            doc = frappe.get_doc({
                "doctype": "Workflow State",
                "workflow_state_name": state_name,
                "name": state_name
            })
            doc.insert(ignore_permissions=True)
            print(f"Created {state_name}")
        else:
            print(f"Workflow State {state_name} already exists")

    frappe.db.commit()
    print("Workflow States sync completed.")
