import frappe

def execute():
    # Load the custom JS from file
    with open('/home/jenifar/slcm_v16/apps/slcm/slcm/slcm/web_form/foundations_for_a_legal_education/foundations_for_a_legal_education.js', 'r') as f:
        js_content = f.read()
        
    # use db_set instead of save
    frappe.db.set_value('Web Form', 'foundations-for-a-legal-education', 'client_script', js_content)
    frappe.db.commit()
    print("Successfully updated webform script in database with db_set")
