import frappe
from slcm.admission.utils.compliance import audit_export

def execute(filters=None):
    filters = filters or {}
    columns = [
        {"label": "Log ID", "fieldname": "name", "fieldtype": "Data", "width": 150},
        {"label": "Action", "fieldname": "action", "fieldtype": "Data", "width": 200},
        {"label": "Reference DocType", "fieldname": "reference_doctype", "fieldtype": "Data", "width": 180},
        {"label": "Reference Name", "fieldname": "reference_name", "fieldtype": "Data", "width": 180},
        {"label": "Performed By", "fieldname": "performed_by", "fieldtype": "Data", "width": 180},
        {"label": "Timestamp", "fieldname": "creation", "fieldtype": "Datetime", "width": 180},
        {"label": "Reason", "fieldname": "reason", "fieldtype": "Data", "width": 250}
    ]
    result = audit_export(
        from_date=filters.get("from_date"),
        to_date=filters.get("to_date"),
        reference_doctype=filters.get("reference_doctype")
    )
    data = result.get("records", [])
    return columns, data
