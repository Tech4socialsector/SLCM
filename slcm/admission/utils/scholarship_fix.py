import frappe
from frappe.utils import flt
from slcm.admission.utils.scholarship_availability import update_scheme_usage

@frappe.whitelist()
def fix_scholarship_counts():
    """
    Recalculates current_beneficiaries, utilized_budget on Scholarship Scheme
    and current_count on Scholarship Scheme Mapping based on Approved applications.
    """
    # Recalculating...

    # 1. Reset
    frappe.db.sql("UPDATE `tabScholarship Scheme` SET current_beneficiaries = 0, utilized_budget = 0")
    frappe.db.sql("UPDATE `tabScholarship Scheme Mapping` SET current_count = 0")
    
    # 2. Re-apply
    apps = frappe.get_all("Scholarship Application", filters={"status": "Approved"}, fields=["name"])
    
    count = 0
    for app_name in apps:
        doc = frappe.get_doc("Scholarship Application", app_name.name)
        mapping_name = doc.find_mapping()
        update_scheme_usage(doc.scholarship_scheme, doc.calculated_benefit, mapping_name=mapping_name)
        count += 1
        
    frappe.db.commit()
    return f"Recalculated {count} applications."
