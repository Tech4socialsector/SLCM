# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}

    # Backend role-based restriction
    user_roles = frappe.get_roles()
    if "Document Verifier" in user_roles and not any(r in user_roles for r in ["PACE Manager", "System Manager", "Admission Admin", "PACE Admission Manager"]):
        filters["assigned_verifier"] = frappe.session.user

    data = get_data(filters)
    chart = get_chart_data(data)
    summary = get_summary(data)

    return get_columns(), data, None, chart, summary


def get_columns():
    return [
        {
            "label": _("Status"),
            "fieldname": "overall_status",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Count"),
            "fieldname": "count",
            "fieldtype": "Int",
            "width": 120
        }
    ]


def get_conditions(filters):
    conditions = []

    if filters.get("academic_year"):
        conditions.append("(academic_year = %(academic_year)s OR academic_year IS NULL OR academic_year = '')")

    if filters.get("programme"):
        conditions.append("programme = %(programme)s")

    if filters.get("assigned_verifier"):
        conditions.append("assigned_verifier = %(assigned_verifier)s")

    return " AND ".join(conditions)


def get_data(filters):
    conditions = get_conditions(filters)
    where_clause = f"WHERE {conditions}" if conditions else ""

    data = frappe.db.sql(f"""
        SELECT
            TRIM(IFNULL(overall_status, 'Pending')) as overall_status,
            COUNT(name) as count
        FROM `tabPACE Document Verification`
        {where_clause}
        GROUP BY TRIM(IFNULL(overall_status, 'Pending'))
    """, filters, as_dict=1)

    return data


def get_chart_data(data):
    if not data:
        return {}

    # Aggregate counts by display label to handle duplicates or mapping
    aggregated_data = {}
    
    color_map = {
        _("Verified"): "#28a745",
        _("Pending"): "#fd7e14",
        _("Rejected"): "#dc3545",
        _("Correction"): "#6f42c1"
    }

    for row in data:
        status = row.overall_status
        if status == "Returned for Correction":
            display_status = _("Correction")
        elif status in ["Verified", "Pending", "Rejected"]:
            display_status = _(status)
        else:
            display_status = _(status) or _("Pending") # Fallback to Pending if empty
            
        aggregated_data[display_status] = aggregated_data.get(display_status, 0) + row.count

    labels = []
    values = []
    colors = []

    for label, count in aggregated_data.items():
        labels.append(label)
        values.append(count)
        colors.append(color_map.get(label, "#ced4da"))

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Status"),
                    "values": values
                }
            ]
        },
        "type": "pie",
        "colors": colors,
        "height": 300
    }


def get_summary(data):
    if not data:
        return []

    total = sum(row.count for row in data)
    pending = sum(row.count for row in data if row.overall_status == "Pending")
    verified = sum(row.count for row in data if row.overall_status == "Verified")

    return [
        {"value": total, "label": _("Total"), "datatype": "Int", "indicator": "Blue"},
        {"value": pending, "label": _("Pending"), "datatype": "Int", "indicator": "Orange"},
        {"value": verified, "label": _("Verified"), "datatype": "Int", "indicator": "Green"}
    ]