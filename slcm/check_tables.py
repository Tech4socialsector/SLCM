import frappe

def execute():
    res = frappe.db.sql("SHOW TABLES LIKE '%Application%'")
    for row in res:
        print(row[0])
