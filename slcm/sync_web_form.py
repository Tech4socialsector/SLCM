import frappe

def execute():
    try:
        # Fetch the web form
        doc = frappe.get_doc("Web Form", "foundations-for-a-legal-education")
        
        # If the document does not have is_standard checked, check it.
        # This will instruct Frappe to export the schema (UI changes) back to the json file.
        doc.is_standard = 1
        
        # We also want to make sure the app context is correct
        doc.module = "SLCM"
        
        # Run standard doc save logic which automatically tracks changes and exports
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        print("Successfully synchronized Web Form to JSON.")
    except Exception as e:
        print(f"Error: {e}")
