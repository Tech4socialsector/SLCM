import frappe
import os

def run():
    # Try to find the site name
    sites_path = "/home/bsoft/slcm-bench-v16/sites"
    site = "slcm.com" # Default assumption
    
    if os.path.exists(os.path.join(sites_path, "currentsite.txt")):
        with open(os.path.join(sites_path, "currentsite.txt"), "r") as f:
            site = f.read().strip()
    
    print(f"Executing for site: {site}")
    
    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()
    
    doctype = "PACE Document Verification"
    table = f"tab{doctype}"
    
    columns = frappe.db.get_table_columns(doctype)
    if "programme" not in columns:
        print("Adding 'programme' column to DB...")
        frappe.db.sql(f"ALTER TABLE `{table}` ADD COLUMN `programme` varchar(255)")
        print("Column added.")
    else:
        print("Column 'programme' already exists.")
        
    print("Clearing cache...")
    frappe.clear_cache(doctype=doctype)
    frappe.clear_cache()
    
    frappe.db.commit()
    print("Done.")

if __name__ == "__main__":
    run()
