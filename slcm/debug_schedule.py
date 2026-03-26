import sys
import os
import json

# Add apps to path
current_dir = os.path.dirname(os.path.abspath(__file__))
# slcm/apps/slcm/slcm
app_dir = os.path.dirname(current_dir)
# slcm/apps/slcm
apps_dir = os.path.dirname(app_dir)
# slcm/apps
bench_dir = os.path.dirname(apps_dir)
# slcm

sys.path.append(bench_dir)
sys.path.append(os.path.join(bench_dir, "apps", "frappe"))
sys.path.append(os.path.join(bench_dir, "apps", "slcm"))

import frappe

def debug_class_schedule():
    frappe.init(site="slcm.local", sites_path=os.path.join(bench_dir, "sites"))
    frappe.connect()
    
    print("--- Class Schedule Meta Fields ---")
    meta = frappe.get_meta("Class Schedule")
    for field in meta.fields:
        if field.fieldtype == "Link" or field.label == "Current Status":
           print(f"Field: {field.fieldname}, Type: {field.fieldtype}, Label: {field.label}, Options: {field.options}")
           
    print("\n--- Custom Fields ---")
    custom_fields = frappe.get_all("Custom Field", filters={"dt": "Class Schedule"}, fields=["fieldname", "fieldtype", "label", "options"])
    for field in custom_fields:
        print(field)

    print("\n--- Property Setters ---")
    prop_setters = frappe.get_all("Property Setter", filters={"doc_type": "Class Schedule"}, fields=["field_name", "property", "value"])
    for prop in prop_setters:
        print(prop)

    print("\n--- Workflows ---")
    workflows = frappe.get_all("Workflow", filters={"document_type": "Class Schedule"}, fields=["name", "workflow_state_field"])
    for wf in workflows:
        print(wf)
        # Get states
        states = frappe.get_all("Workflow Document State", filters={"parent": wf.name}, fields=["state", "doc_status"])
        print("States:", states)

    frappe.destroy()

if __name__ == "__main__":
    debug_class_schedule()
