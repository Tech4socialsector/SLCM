import frappe
import os
import json

def fix_doctypes():
    doctype_dir = frappe.get_app_path('slcm', 'slcm', 'doctype')
    for d in os.listdir(doctype_dir):
        json_path = os.path.join(doctype_dir, d, d + '.json')
        if os.path.exists(json_path):
            doc_name = d.replace('_', ' ').title().replace(' Id ', ' ID ')
            # special cases
            if doc_name == 'Rfid Device': doc_name = 'RFID Device'
            if doc_name == 'Fa Mfa Application': doc_name = 'FA MFA Application'
            
            # just read the doctype name from the JSON
            with open(json_path, 'r') as f:
                data = json.load(f)
                actual_name = data.get('name')
                
            if actual_name and frappe.db.exists('DocType', actual_name):
                db_module = frappe.db.get_value('DocType', actual_name, 'module')
                if db_module != 'SLCM':
                    print(f"Fixing DB module for {actual_name} from {db_module} to SLCM")
                    frappe.db.set_value('DocType', actual_name, 'module', 'SLCM')
                    # And delete from DB the custom field if it was customized, wait no, just fix module
                    frappe.db.commit()
    print("Done")
