import frappe

def execute():
    try:
        frappe.db.sql("ALTER TABLE `tabStudent Master` DROP COLUMN `id_validity`")
        frappe.db.commit()
        print("Dropped column id_validity")
    except Exception as e:
        print("Error:", str(e))
