import frappe
from frappe.utils import cstr

def execute():
    # Load the custom JS from file
    with open('/home/jenifar/slcm_v16/apps/slcm/slcm/slcm/web_form/foundations_for_a_legal_education/foundations_for_a_legal_education.js', 'r') as f:
        js_content = f.read()
        
    # Get the document
    doc = frappe.get_doc('Web Form', 'foundations-for-a-legal-education')
    
    # Update field
    doc.client_script = js_content
    
    # Save to db
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print("Successfully updated webform script in database")
