import frappe

def execute():
    res = frappe.db.sql("SELECT count(*) FROM `tabStudent Master`")
    print("Row count:", res[0][0])
    
    # Select all distinct id_validity values
    res2 = frappe.db.sql("SELECT DISTINCT id_validity FROM `tabStudent Master`")
    print("Distinct id_validity:", res2)
