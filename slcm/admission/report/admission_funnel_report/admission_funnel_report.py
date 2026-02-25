import frappe
from slcm.admission.utils.compliance import admission_funnel

def execute(filters=None):
    filters = filters or {}
    columns = [
        {"label": "Stage", "fieldname": "stage", "fieldtype": "Data", "width": 250},
        {"label": "Count", "fieldname": "count", "fieldtype": "Int", "width": 120},
        {"label": "Conversion %", "fieldname": "conversion", "fieldtype": "Percent", "width": 150}
    ]
    result = admission_funnel(cycle=filters.get("admission_cycle"))
    funnel = result.get("funnel", {})
    data = []
    prev = None
    for stage, count in funnel.items():
        conversion = round((count / prev * 100), 1) if prev and prev > 0 else 100.0
        data.append({"stage": stage, "count": count, "conversion": conversion})
        prev = count
    return columns, data
