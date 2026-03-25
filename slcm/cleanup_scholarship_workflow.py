import frappe

def execute():
    # 1. Delete the Workflow record
    if frappe.db.exists("Workflow", "Scholarship Application Workflow"):
        frappe.delete_doc("Workflow", "Scholarship Application Workflow", ignore_permissions=True)
        print("Deleted Workflow: Scholarship Application Workflow")
    
    # 2. Clear the workflow_state field in the Scholarship Application table
    # This field is often added dynamically or exists as a custom field
    try:
        frappe.db.sql("UPDATE `tabScholarship Application` SET workflow_state = NULL")
        print("Cleared workflow_state for Scholarship Application")
    except Exception as e:
        print(f"Note: Could not clear workflow_state (it might not exist): {e}")

    # 3. Check for Custom Field 'workflow_state' on Scholarship Application
    if frappe.db.exists("Custom Field", {"dt": "Scholarship Application", "fieldname": "workflow_state"}):
        frappe.delete_doc("Custom Field", "Scholarship Application-workflow_state", ignore_permissions=True)
        print("Deleted Custom Field: Scholarship Application-workflow_state")

    # 4. Clear any other workflow related states if they are stuck
    # Sometimes Frappe stores current state in the document itself but it should be null if no workflow exists
    
    frappe.db.commit()
    print("Cleanup complete. Please run 'bench migrate' or 'bench restart'.")

if __name__ == "__main__":
    execute()
