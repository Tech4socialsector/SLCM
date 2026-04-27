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

    # Returning empty summary as requested to remove number cards
    return get_columns(), data, None, chart, []


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
        conditions.append("academic_year = %(academic_year)s")

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
            overall_status,
            COUNT(name) as count
        FROM `tabPACE Document Verification`
        {where_clause}
        GROUP BY overall_status
    """, filters, as_dict=1)

    return data


def get_chart_data(data):
    if not data:
        return {}

    labels = []
    values = []
    
    # Define colors for each status
    color_map = {
        "Verified": "#28a745",          # Green
        "Pending": "#fd7e14",           # Orange
        "Rejected": "#dc3545",          # Red
        "Returned for Correction": "#6f42c1"  # Purple
    }
    
    colors = []

    for row in data:
        status = row.overall_status or "Unknown"
        # Extremely short labels to avoid overlapping in legend
        if status == "Returned for Correction":
            display_status = _("Correction")
        elif status == "Verified":
            display_status = _("Verified")
        elif status == "Pending":
            display_status = _("Pending")
        elif status == "Rejected":
            display_status = _("Rejected")
        else:
            display_status = _(status)
            
        labels.append(display_status)
        values.append(row.count)
        colors.append(color_map.get(status, "#ced4da"))

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
    # This is still here but not used in execute to satisfy the user request of removing cards
    return []