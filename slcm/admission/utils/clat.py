import frappe
import csv
from frappe.utils import now

def import_clat_ranks(file_url, cycle):
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    content = file_doc.get_content()
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    reader = csv.DictReader(content.splitlines())
    imported = 0
    errors = []
    for row in reader:
        try:
            process_rank_row(row, cycle)
            imported += 1
        except Exception as e:
            errors.append(f"Row {imported + 1}: {str(e)}")
    return {"imported": imported, "errors": errors}

def process_rank_row(row, cycle):
    applicant = frappe.db.get_value(
        "Applicant",
        {"email": row.get("email"), "admission_cycle": cycle},
        "name"
    )
    if not applicant:
        raise Exception(f"Applicant not found for email: {row.get('email')}")
    pref = frappe.db.get_value(
        "Applicant Campus Preference",
        {"applicant": applicant, "admission_cycle": cycle},
        "name"
    )
    if pref:
        frappe.db.set_value("Applicant Campus Preference", pref, {
            "clat_rank": row.get("air_rank"),
            "clat_category_rank": row.get("category_rank")
        })