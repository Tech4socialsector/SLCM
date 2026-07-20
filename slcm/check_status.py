import frappe

def execute():
    res = frappe.db.sql("SELECT DISTINCT status FROM `tabPACE Application`", as_dict=True)
    for r in res:
        print(r)
