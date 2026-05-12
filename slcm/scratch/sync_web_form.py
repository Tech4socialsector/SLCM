import frappe
from frappe.modules.import_file import import_file_by_path
import os

def sync_web_form():
    path = "/home/bsoft/slcm-bench-v16/apps/slcm/slcm/pace/web_form/pace_application_form/pace_application_form.json"
    if os.path.exists(path):
        import_file_by_path(path, force=True)
        frappe.db.commit()
        print("Synced successfully")
    else:
        print(f"Path not found: {path}")

if __name__ == "__main__":
    sync_web_form()
