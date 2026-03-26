import frappe

def run():
    # 1. Delete all Applicant Fee Component Child rows where fee_component is 'Scholarship'
    # These are legacy rows that are no longer needed because scholarship is now tracked in its own field.
    deleted_count = frappe.db.sql("""
        DELETE FROM `tabApplicant Fee Component Child`
        WHERE fee_component = 'Scholarship'
    """)
    print(f"Deleted {deleted_count} legacy scholarship fee component rows.")

    # 2. Recalculate totals for all affected AFA documents
    # We find AFAs that were likely affected (those for which we deleted rows)
    # Actually, let's just refresh all AFAs that have scholarship_amount > 0 to be safe.
    afas = frappe.get_all("Applicant Fee Assignment", filters={"docstatus": ["!=", 2]}, fields=["name"])
    
    updated_count = 0
    for entry in afas:
        doc = frappe.get_doc("Applicant Fee Assignment", entry.name)
        # Calling validate() will trigger apply_scholarship() and calculate_totals()
        doc.apply_scholarship()
        doc.calculate_totals()
        
        # Save directly to DB to avoid status changes/hooks if not necessary,
        # but here we want to ensure the final_payable_amount is correct.
        doc.db_set("scholarship_amount", doc.scholarship_amount)
        doc.db_set("scholarship_applied", doc.scholarship_applied)
        doc.db_set("total_amount", doc.total_amount)
        doc.db_set("final_payable_amount", doc.final_payable_amount)
        updated_count += 1

    print(f"Updated totals for {updated_count} Applicant Fee Assignments.")
    frappe.db.commit()

if __name__ == "__main__":
    run()
