import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}
        
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    report_summary = get_report_summary(data)
    
    return columns, data, None, chart, report_summary

def get_columns():
    return [
        {"label": _("Rank"), "fieldname": "overall_rank", "fieldtype": "Int", "width": 60},
        {"label": _("Part A Rank"), "fieldname": "part_a_rank", "fieldtype": "Int", "width": 80},
        {"label": _("Part B Rank"), "fieldname": "part_b_rank", "fieldtype": "Int", "width": 80},
        {"label": _("Candidate Name"), "fieldname": "candidate_name", "fieldtype": "Data", "width": 180},
        {"label": _("Applicant ID"), "fieldname": "applicant_id", "fieldtype": "Link", "options": "Applicant", "width": 120},
        {"label": _("Programme"), "fieldname": "program", "fieldtype": "Link", "options": "Programme", "width": 140},
        {"label": _("Category"), "fieldname": "actual_category", "fieldtype": "Data", "width": 120},
        {"label": _("Part A Score"), "fieldname": "entrance_score", "fieldtype": "Float", "width": 100},
        {"label": _("Part B Score"), "fieldname": "interview_score", "fieldtype": "Float", "width": 100},
        {"label": _("Total Score"), "fieldname": "total_score", "fieldtype": "Float", "width": 100},
        {"label": _("Percentile"), "fieldname": "percentile_score", "fieldtype": "Float", "precision": 5, "width": 110},
        {"label": _("Allocated / Shortlisted Category"), "fieldname": "shortlisted_category", "fieldtype": "Data", "width": 180},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100}
    ]

def get_latest_parent_names(doctype, filters, extra_filters=None):
    """
    Finds the latest parent document name(s) for the given admission_cycle, campus, and optional program.
    If program is specified, returns the single latest parent doc.
    If program is not specified, returns the latest parent doc per distinct program.
    """
    cycle = filters.get("admission_cycle")
    campus = filters.get("campus")
    program = filters.get("program")

    base_filters = {"admission_cycle": cycle, "campus": campus}
    if extra_filters:
        base_filters.update(extra_filters)

    if program:
        base_filters["program"] = program
        active_filters = dict(base_filters)
        active_filters["status"] = ["!=", "Superseded"]
        doc_name = frappe.db.get_value(doctype, active_filters, "name", order_by="creation desc")
        if not doc_name:
            doc_name = frappe.db.get_value(doctype, base_filters, "name", order_by="creation desc")
        return [doc_name] if doc_name else []

    all_docs = frappe.get_all(doctype, filters=base_filters, fields=["name", "program", "status", "creation"], order_by="creation desc")
    latest_by_prog = {}
    for d in all_docs:
        prog = d.program or "ALL"
        if prog not in latest_by_prog:
            latest_by_prog[prog] = d.name
        elif d.status != "Superseded" and frappe.db.get_value(doctype, latest_by_prog[prog], "status") == "Superseded":
            latest_by_prog[prog] = d.name
    return list(latest_by_prog.values())

def get_data(filters):
    stage = filters.get("merit_processing_stage") or "Final Allotment Ranking"
    if stage == "Part A Ranking":
        return get_part_a_data(filters)
    elif stage == "Seat Allocation":
        return get_seat_allocation_data(filters)
    else:
        return get_final_allotment_data(filters)

def get_part_a_data(filters):
    parents = get_latest_parent_names("Shortlisting Merit List", filters)
    if not parents:
        return []

    query = """
        SELECT
            mla.shortlist_rank as overall_rank,
            mla.shortlist_rank as part_a_rank,
            0 as part_b_rank,
            mla.candidate_name,
            mla.applicant_id,
            mla.program,
            mla.actual_category,
            mla.nlsat_part_a_score as entrance_score,
            0 as interview_score,
            mla.nlsat_part_a_score as total_score,
            mla.percentile_score as percentile_score,
            mla.shortlist_category as shortlisted_category,
            mla.shortlist_status as status
        FROM
            `tabShortlisting Merit Candidate` mla
        WHERE
            mla.parent IN %(parents)s
            AND mla.parentfield = 'shortlist_applicants'
        ORDER BY
            CASE WHEN mla.shortlist_rank IS NULL OR mla.shortlist_rank = 0 THEN 999999 ELSE mla.shortlist_rank END ASC,
            mla.nlsat_part_a_score DESC
    """
    return frappe.db.sql(query, {"parents": parents}, as_dict=True)

def get_final_allotment_data(filters):
    parents = get_latest_parent_names("Merit List", filters, extra_filters={"merit_processing_stage": "Final Allotment Ranking"})
    if not parents:
        return []

    query = """
        SELECT
            mla.overall_rank,
            mla.part_a_rank,
            mla.part_b_rank,
            mla.candidate_name,
            mla.applicant_id,
            mla.program,
            mla.actual_category,
            mla.entrance_score,
            mla.interview_score,
            mla.total_score,
            mla.percentile_score,
            mla.shortlist_category as shortlisted_category,
            mla.status
        FROM
            `tabMerit List Applicant` mla
        WHERE
            mla.parent IN %(parents)s
            AND mla.parentfield = 'merit_applicants'
        ORDER BY
            CASE WHEN mla.overall_rank IS NULL OR mla.overall_rank = 0 THEN 999999 ELSE mla.overall_rank END ASC,
            mla.total_score DESC
    """
    return frappe.db.sql(query, {"parents": parents}, as_dict=True)

def get_seat_allocation_data(filters):
    parents = get_latest_parent_names("Seat Allocation", filters)
    if not parents:
        return []

    query = """
        SELECT
            sa.overall_rank,
            sa.shortlist_rank as part_a_rank,
            0 as part_b_rank,
            sa.candidate_name,
            sa.applicant_id,
            sa.program,
            sa.actual_category,
            sa.nlsat_part_a_score as entrance_score,
            sa.nlsat_part_b_score as interview_score,
            sa.total_score,
            sa.percentile_score,
            sa.allocated_category as shortlisted_category,
            sa.selection_status as status
        FROM
            `tabSeat Selection Applicant` sa
        WHERE
            sa.parent IN %(parents)s
        ORDER BY
            CASE WHEN sa.overall_rank IS NULL OR sa.overall_rank = 0 THEN 999999 ELSE sa.overall_rank END ASC,
            sa.total_score DESC
    """
    return frappe.db.sql(query, {"parents": parents}, as_dict=True)

def get_chart(data):
    return None

def get_report_summary(data):
    if not data:
        return []

    selected = len([d for d in data if d.status in ["Selected", "Shortlisted"]])
    waitlisted = len([d for d in data if d.status == "Waitlisted"])
    rejected = len([d for d in data if d.status == "Rejected"])
    total = len(data)

    return [
        {"value": total, "label": _("Total Applicants"), "indicator": "Blue", "datatype": "Int"},
        {"value": selected, "label": _("Selected/Shortlisted"), "indicator": "Green", "datatype": "Int"},
        {"value": waitlisted, "label": _("Waitlisted"), "indicator": "Orange", "datatype": "Int"},
        {"value": rejected, "label": _("Rejected"), "indicator": "Red", "datatype": "Int"}
    ]
