import frappe
for dt in ["Admission Application", "Applicant"]:
    exists = frappe.db.exists("DocType", dt)
    print(f"DocType {dt} exists: {exists}")
    if exists:
        meta = frappe.get_meta(dt)
        print(f"Fields for {dt}: {[f.fieldname for f in meta.fields if f.fieldtype not in ('Section Break','Column Break')]}")
