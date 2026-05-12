import frappe

def execute():
    try:
        # Revert back to Law of History
        frappe.db.sql("""UPDATE `tabFA MFA Application` SET course = '8j843sfvne' WHERE name = 'FAMFA-2026-00001'""")
        frappe.db.commit()
    except Exception as e:
        pass
        
    return True
