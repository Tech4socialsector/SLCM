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
            "label": _("Allocated Category"),
            "fieldname": "allocated_category",
            "fieldtype": "Data",
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
    # 1. Resolve relevant Seat Allocations
    sa_filters = {"docstatus": ["<", 2]}
    
    if filters.get("admission_cycle"):
        sa_filters["admission_cycle"] = filters.get("admission_cycle")
    elif filters.get("admission_year"):
        cycles = frappe.get_all("Admission Cycle", filters={"admission_year": filters.get("admission_year")}, pluck="name")
        if not cycles: return []
        sa_filters["admission_cycle"] = ["in", cycles]
        
    if filters.get("campus"):
        sa_filters["campus"] = filters.get("campus")

    raw_allocations = frappe.get_all("Seat Allocation", 
        filters=sa_filters, 
        fields=["name", "campus", "admission_cycle", "program_level", "status", "modified"],
        order_by="modified desc"
    )

    # Dedup: keep only the most relevant (Published > Allocated > Draft) per (campus, cycle, level)
    dedup_map = {}
    status_priority = {"Published": 2, "Allocated": 1, "Draft": 0}
    for sa in raw_allocations:
        key = (sa.campus, sa.admission_cycle, sa.program_level)
        existing = dedup_map.get(key)
        curr_prio = status_priority.get(sa.status, -1)
        prev_prio = status_priority.get(existing.status, -1) if existing else -1
        if not existing or curr_prio > prev_prio:
            dedup_map[key] = sa

    sa_names = [sa.name for sa in dedup_map.values()]
    if not sa_names:
        return []

    # 2. Fetch Applicants from those allocations
    conditions = ["app.parent IN %(sa_names)s"]
    params = {"sa_names": sa_names}

    if filters.get("program"):
        conditions.append("app.program = %(program)s")
        params["program"] = filters.get("program")

    if filters.get("selection_status"):
        conditions.append("app.selection_status = %(selection_status)s")
        params["selection_status"] = filters.get("selection_status")

    where_clause = " WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            app.candidate_name,
            app.applicant_id,
            app.program,
            app.allocated_category,
            app.selection_status,
            app.total_score,
            app.overall_rank
        FROM
            `tabSeat Selection Applicant` app
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
