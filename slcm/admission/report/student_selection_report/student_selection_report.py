# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("Candidate Name"),
            "fieldname": "candidate_name",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": _("Applicant ID"),
            "fieldname": "applicant_id",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Program"),
            "fieldname": "program",
            "fieldtype": "Link",
            "options": "Program",
            "width": 150
        },
        {
            "label": _("Category"),
            "fieldname": "reservation_category",
            "fieldtype": "Link",
            "options": "Admission Category",
            "width": 120
        },
        {
            "label": _("Selection Status"),
            "fieldname": "selection_status",
            "fieldtype": "Select",
            "width": 120
        },
        {
            "label": _("Total Score"),
            "fieldname": "total_score",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("Overall Rank"),
            "fieldname": "overall_rank",
            "fieldtype": "Int",
            "width": 100
        }
    ]

def get_data(filters):
    conditions = []
    params = {}

    if filters.get("admission_year"):
        cycles = frappe.get_all("Admission Cycle", 
            filters={"parent": filters.get("admission_year")}, 
            fields=["name"]
        )
        cycle_names = [c.name for c in cycles]
        if cycle_names:
            conditions.append("sa.admission_cycle IN %(cycle_names)s")
            params["cycle_names"] = cycle_names
        else:
            return [] # No cycles in year = no students

    if filters.get("admission_cycle"):
        conditions.append("sa.admission_cycle = %(admission_cycle)s")
        params["admission_cycle"] = filters.get("admission_cycle")
    
    if filters.get("campus"):
        conditions.append("sa.campus = %(campus)s")
        params["campus"] = filters.get("campus")

    if filters.get("program"):
        conditions.append("app.program = %(program)s")
        params["program"] = filters.get("program")

    if filters.get("selection_status"):
        conditions.append("app.selection_status = %(selection_status)s")
        params["selection_status"] = filters.get("selection_status")

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    sql = f"""
        SELECT
            app.candidate_name,
            app.applicant_id,
            app.program,
            app.reservation_category,
            app.selection_status,
            app.total_score,
            app.overall_rank
        FROM
            `tabSeat Selection Applicant` app
        INNER JOIN
            `tabSeat Allocation` sa ON app.parent = sa.name
        {where_clause}
        ORDER BY
            app.program ASC, app.overall_rank ASC
    """

    return frappe.db.sql(sql, params, as_dict=True)

def get_chart_data(columns, data, filters):
    if not data:
        return None

    status_counts = {}
    for d in data:
        status = d.get("selection_status") or "N/A"
        status_counts[status] = status_counts.get(status, 0) + 1

    labels = sorted(status_counts.keys())
    values = [status_counts[l] for l in labels]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": "Status Count", "values": values}]
        },
        "type": "pie",
        "colors": ["#ffa00a", "#1fb5ad", "#ff5858"]
    }
