# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from collections import defaultdict

def execute(filters=None):
    if not filters:
        filters = {}
        
    # Backend role-based restriction
    user_roles = frappe.get_roles()
    if "Document Verifier" in user_roles and not any(r in user_roles for r in ["PACE Manager", "System Manager", "Admission Admin", "PACE Admission Manager"]):
        filters["assigned_verifier"] = frappe.session.user

    data = get_raw_data(filters)

    columns = get_columns()
    table_data = get_table_data(data)

    chart = get_chart_data(data)

    # Returning empty summary as requested to remove number cards
    return columns, table_data, None, chart, []


# -----------------------------
# 🔹 Columns (Table View)
# -----------------------------
def get_columns():
    return [
        {"label": _("Application"), "fieldname": "application", "fieldtype": "Link", "options": "PACE Application", "width": 180},
        {"label": _("Applicant Name"), "fieldname": "applicant_name", "fieldtype": "Data", "width": 200},
        {"label": _("Academic Year"), "fieldname": "academic_year", "fieldtype": "Link", "options": "Academic Year", "width": 120},
        {"label": _("Programme"), "fieldname": "programme", "fieldtype": "Link", "options": "PACE Programme", "width": 150},
        {"label": _("Verifier"), "fieldname": "assigned_verifier", "fieldtype": "Link", "options": "User", "width": 150},
        {"label": _("Status"), "fieldname": "overall_status", "fieldtype": "Data", "width": 130},
        {"label": _("Verified On"), "fieldname": "verified_on", "fieldtype": "Datetime", "width": 180},
    ]


# -----------------------------
# 🔹 Conditions
# -----------------------------
def get_conditions(filters):
    conditions = []

    if filters.get("from_date"):
        conditions.append("DATE(IFNULL(verified_on, creation)) >= %(from_date)s")

    if filters.get("to_date"):
        conditions.append("DATE(IFNULL(verified_on, creation)) <= %(to_date)s")

    if filters.get("programme"):
        conditions.append("programme = %(programme)s")

    if filters.get("academic_year"):
        conditions.append("academic_year = %(academic_year)s")

    if filters.get("assigned_verifier"):
        conditions.append("assigned_verifier = %(assigned_verifier)s")

    return " AND ".join(conditions)


# -----------------------------
# 🔹 Fetch Raw Data
# -----------------------------
def get_raw_data(filters):
    conditions = get_conditions(filters)
    where_clause = f"WHERE {conditions}" if conditions else ""

    return frappe.db.sql(f"""
        SELECT
            name,
            application,
            applicant_name,
            academic_year,
            programme,
            assigned_verifier,
            overall_status,
            verified_on,
            creation
        FROM `tabPACE Document Verification`
        {where_clause}
        ORDER BY IFNULL(verified_on, creation) ASC
    """, filters, as_dict=True)


# -----------------------------
# 🔹 Table Data
# -----------------------------
def get_table_data(data):
    return data


# -----------------------------
# 🔹 Chart Data (Multi-Dataset Bar Chart)
# -----------------------------
def get_chart_data(data):
    if not data:
        return {}

    # Group by Date
    date_data = defaultdict(lambda: {
        "Assigned": 0,
        "Verified": 0,
        "Pending": 0,
        "Rejected": 0,
        "Returned for Correction": 0
    })

    for row in data:
        dt = (row.verified_on or row.creation).date()
        date_str = dt.strftime("%Y-%m-%d")
        
        date_data[date_str]["Assigned"] += 1
        
        status = row.overall_status
        if status in date_data[date_str]:
            date_data[date_str][status] += 1

    labels = sorted(date_data.keys())
    
    datasets = [
        {
            "name": _("Assigned"),
            "values": [date_data[l]["Assigned"] for l in labels],
            "chartType": "bar"
        },
        {
            "name": _("Verified"),
            "values": [date_data[l]["Verified"] for l in labels],
            "chartType": "bar"
        },
        {
            "name": _("Pending"),
            "values": [date_data[l]["Pending"] for l in labels],
            "chartType": "bar"
        },
        {
            "name": _("Rejected"),
            "values": [date_data[l]["Rejected"] for l in labels],
            "chartType": "bar"
        },
        {
            "name": _("Correction"),
            "values": [date_data[l]["Returned for Correction"] for l in labels],
            "chartType": "bar"
        }
    ]

    return {
        "data": {
            "labels": labels,
            "datasets": datasets
        },
        "type": "bar",
        "colors": ["#4567b7", "#28a745", "#fd7e14", "#dc3545", "#6f42c1"], # Assigned (Blue), Verified (Green), Pending (Orange), Rejected (Red), Correction (Purple)
        "height": 300
    }


def get_summary(data):
    return []