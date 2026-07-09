import frappe
from slcm.admission.utils.compliance import seat_utilization

def execute(filters=None):
    filters = filters or {}
    columns = [
        {"label": "Campus", "fieldname": "campus", "fieldtype": "Link", "options": "Company", "width": 180},
        {"label": "Programme", "fieldname": "program", "fieldtype": "Link", "options": "Programme", "width": 180},
        {"label": "Category", "fieldname": "category", "fieldtype": "Data", "width": 150},
        {"label": "Total Seats", "fieldname": "intake_capacity", "fieldtype": "Int", "width": 120}
    ]
    result = seat_utilization(cycle=filters.get("admission_cycle"))
    data = result.get("data", [])
    return columns, data
