import frappe
meta = frappe.get_meta('Applicant')
print(f"Email fields: {[f.fieldname for f in meta.fields if 'email' in f.fieldname]}")
