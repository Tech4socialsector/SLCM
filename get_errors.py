
import frappe
import json

def get_recent_errors():
    frappe.init(site="slcm.com")
    frappe.connect()
    errors = frappe.get_all("Error Log", 
                           fields=["name", "method", "error", "creation"], 
                           order_by="creation desc", 
                           limit=10)
    print(json.dumps(errors, indent=4, default=str))

if __name__ == "__main__":
    get_recent_errors()
