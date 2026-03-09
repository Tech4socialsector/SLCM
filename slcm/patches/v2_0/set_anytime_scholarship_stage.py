import frappe
 
def execute():
    """
    Sets all existing Scholarship Schemes to 'Anytime' stage availability
    so they are visible to applicants before selection results are published.
    """
    frappe.db.sql("UPDATE `tabScholarship Scheme` SET stage_availability='Anytime'")
    frappe.db.commit()
 