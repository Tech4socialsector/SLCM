# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(columns, data, filters)
    return columns, data, None, chart

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
            "fieldtype": "Link",
            "options": "Applicant",
            "width": 120
        },
        {
            "label": _("Gender"),
            "fieldname": "gender",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Programme"),
            "fieldname": "program",
            "fieldtype": "Link",
            "options": "Programme",
            "width": 120
        },
        {
            "label": _("Actual Category"),
            "fieldname": "actual_category",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Vertical Category"),
            "fieldname": "vertical_category",
            "fieldtype": "Link",
            "options": "Admission Category",
            "width": 130
        },
        {
            "label": _("Shortlisted Category"),
            "fieldname": "shortlisted_category",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Horizontal Categories"),
            "fieldname": "horizontal_categories",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Karnataka"),
            "fieldname": "compartmentalized_category",
            "fieldtype": "Data",
            "width": 100
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
            "label": _("Part A"),
            "fieldname": "nlsat_part_a_score",
            "fieldtype": "Float",
            "width": 80
        },
        {
            "label": _("Part B"),
            "fieldname": "nlsat_part_b_score",
            "fieldtype": "Float",
            "width": 80
        },
        {
            "label": _("Overall Rank"),
            "fieldname": "overall_rank",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Category Rank"),
            "fieldname": "category_rank",
            "fieldtype": "Int",
            "width": 110
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
        fields=["name", "campus", "admission_cycle", "program_level", "program", "status", "modified"],
        order_by="modified desc"
    )

    if raw_allocations:
        # Dedup: keep only the most relevant per (campus, cycle, level, program)
        dedup_map = {}
        status_priority = {"Published": 2, "Allocated": 1, "Draft": 0}
        for sa in raw_allocations:
            key = (sa.campus, sa.admission_cycle, sa.program_level, sa.get("program"))
            existing = dedup_map.get(key)
            curr_prio = status_priority.get(sa.status, -1)
            prev_prio = status_priority.get(existing.status, -1) if existing else -1
            if not existing or curr_prio > prev_prio:
                dedup_map[key] = sa

        sa_names = [sa.name for sa in dedup_map.values()]

        conditions = ["app.parent IN %(sa_names)s"]
        params = {"sa_names": sa_names}

        if filters.get("program"):
            conditions.append("app.program = %(program)s")
            params["program"] = filters.get("program")

        if filters.get("selection_status"):
            conditions.append("app.selection_status = %(selection_status)s")
            params["selection_status"] = filters.get("selection_status")
        
        if filters.get("vertical_category"):
            conditions.append("app.vertical_category = %(v_cat)s")
            params["v_cat"] = filters.get("vertical_category")

        if filters.get("shortlisted_category"):
            conditions.append("COALESCE(NULLIF(app.allocated_category, ''), app.vertical_category, app.actual_category) = %(shortlisted_cat)s")
            params["shortlisted_cat"] = filters.get("shortlisted_category")

        where_clause = " WHERE " + " AND ".join(conditions)

        sql = f"""
            SELECT
                app.admission_rank,
                app.candidate_name,
                app.applicant_id,
                a.gender,
                app.program,
                app.actual_category,
                app.vertical_category,
                COALESCE(NULLIF(app.allocated_category, ''), app.vertical_category, app.actual_category) as shortlisted_category,
                app.horizontal_categories,
                app.compartmentalized_category,
                app.selection_status,
                app.total_score,
                app.nlsat_part_a_score,
                app.nlsat_part_b_score,
                app.overall_rank,
                app.category_rank
            FROM
                `tabSeat Selection Applicant` app
            LEFT JOIN
                `tabApplicant` a ON app.applicant_id = a.name
            {where_clause}
            ORDER BY
                app.program ASC, 
                CASE WHEN app.admission_rank IS NULL OR app.admission_rank = 0 THEN 999999 ELSE app.admission_rank END ASC,
                app.overall_rank ASC
        """
        data = frappe.db.sql(sql, params, as_dict=True)
        if data:
            return data

    # 2. Fallback to Shortlisting Merit List if Seat Allocation is empty
    sp_filters = {"docstatus": ["<", 2]}
    if filters.get("admission_cycle"):
        sp_filters["admission_cycle"] = filters.get("admission_cycle")
    elif filters.get("admission_year"):
        cycles = frappe.get_all("Admission Cycle", filters={"admission_year": filters.get("admission_year")}, pluck="name")
        if not cycles: return []
        sp_filters["admission_cycle"] = ["in", cycles]

    if filters.get("campus"):
        sp_filters["campus"] = filters.get("campus")

    raw_sp = frappe.get_all("Shortlisting Merit List",
        filters=sp_filters,
        fields=["name", "campus", "admission_cycle", "program_level", "program", "status", "modified"],
        order_by="modified desc"
    )

    if not raw_sp:
        return []

    sp_dedup = {}
    for sp in raw_sp:
        key = (sp.campus, sp.admission_cycle, sp.program_level, sp.get("program"))
        if key not in sp_dedup:
            sp_dedup[key] = sp

    sp_names = [sp.name for sp in sp_dedup.values()]

    conditions = ["app.parent IN %(sp_names)s", "app.parentfield = 'shortlist_applicants'"]
    params = {"sp_names": sp_names}

    if filters.get("program"):
        conditions.append("app.program = %(program)s")
        params["program"] = filters.get("program")

    if filters.get("selection_status"):
        conditions.append("app.shortlist_status = %(selection_status)s")
        params["selection_status"] = filters.get("selection_status")

    if filters.get("vertical_category"):
        conditions.append("(app.vertical_category = %(v_cat)s OR app.actual_category = %(v_cat)s)")
        params["v_cat"] = filters.get("vertical_category")

    if filters.get("shortlisted_category"):
        conditions.append("COALESCE(NULLIF(app.shortlist_category, ''), app.vertical_category, app.actual_category) = %(shortlisted_cat)s")
        params["shortlisted_cat"] = filters.get("shortlisted_category")

    where_clause = " WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            app.shortlist_rank as admission_rank,
            app.candidate_name,
            app.applicant_id,
            a.gender,
            app.program,
            app.actual_category,
            COALESCE(NULLIF(app.vertical_category, ''), app.actual_category) as vertical_category,
            COALESCE(NULLIF(app.shortlist_category, ''), app.vertical_category, app.actual_category) as shortlisted_category,
            app.horizontal_categories,
            app.compartmentalized_category,
            app.shortlist_status as selection_status,
            app.nlsat_part_a_score as total_score,
            app.nlsat_part_a_score,
            0 as nlsat_part_b_score,
            app.shortlist_rank as overall_rank,
            app.category_rank
        FROM
            `tabShortlisting Merit Candidate` app
        LEFT JOIN
            `tabApplicant` a ON app.applicant_id = a.name
        {where_clause}
        ORDER BY
            app.program ASC, 
            app.shortlist_rank ASC
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

