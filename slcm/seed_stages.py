import frappe

def seed():
    frappe.db.sql("""
        UPDATE `tabAdmission Stage Config`
        SET applicable_workflow = 'All'
        WHERE applicable_workflow IS NULL OR applicable_workflow = ''
    """)
    frappe.db.commit()
    print("Done.")

if __name__ == "__main__":
    seed()
