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
        {"label": _("Category"), "fieldname": "actual_category", "fieldtype": "Data", "width": 120},
        {"label": _("Part A Score"), "fieldname": "entrance_score", "fieldtype": "Float", "width": 100},
        {"label": _("Part B Score"), "fieldname": "interview_score", "fieldtype": "Float", "width": 100},
        {"label": _("Total Score"), "fieldname": "total_score", "fieldtype": "Float", "width": 100},
        {"label": _("Percentile"), "fieldname": "percentile_score", "fieldtype": "Percent", "width": 100},
        {"label": _("Shortlisted Category"), "fieldname": "shortlisted_category", "fieldtype": "Data", "width": 150},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100}
    ]

def get_data(filters):
    if filters.get("merit_processing_stage") in ["Part A Ranking", "Shortlisting Rank List"]:
        return get_part_a_data(filters)
    else:
        return get_final_allotment_data(filters)

def get_part_a_data(filters):
    sp_filters = {"docstatus": ["<", 2], "status": ["!=", "Superseded"]}
    
    if filters.get("admission_cycle"):
        sp_filters["admission_cycle"] = filters.get("admission_cycle")
    elif filters.get("admission_year"):
        cycles = frappe.get_all("Admission Cycle", filters={"admission_year": filters.get("admission_year")}, pluck="name")
        if not cycles:
            return []
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

    # Dedup: keep the newest non-superseded shortlist per (campus, cycle, program_level, program)
    sp_dedup = {}
    for sp in raw_sp:
        key = (sp.campus, sp.admission_cycle, sp.program_level, sp.get("program"))
        if key not in sp_dedup:
            sp_dedup[key] = sp

    target_sps = list(sp_dedup.values())
    if filters.get("program"):
        target_sps = [sp for sp in target_sps if not sp.get("program") or sp.get("program") == filters.get("program")]

    sp_names = [sp.name for sp in target_sps]
    if not sp_names:
        return []

    conditions = ["mla.parent IN %(sp_names)s", "mla.parentfield = 'shortlist_applicants'"]
    params = {"sp_names": sp_names}

    if filters.get("program"):
        conditions.append("mla.program = %(program)s")
        params["program"] = filters.get("program")

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            mla.shortlist_rank as overall_rank,
            mla.shortlist_rank as part_a_rank,
            0 as part_b_rank,
            mla.candidate_name,
            mla.applicant_id,
            mla.actual_category,
            mla.nlsat_part_a_score as entrance_score,
            0 as interview_score,
            mla.nlsat_part_a_score as total_score,
            etsa.percentile as percentile_score,
            mla.shortlist_category as shortlisted_category,
            mla.shortlist_status as status
        FROM
            `tabShortlisting Merit Candidate` mla
        JOIN
            `tabShortlisting Merit List` ml ON mla.parent = ml.name
        LEFT JOIN
            `tabEntrance Test Seat Allocation` etsa ON mla.applicant_id = etsa.applicant
        WHERE
            {where_clause}
        ORDER BY
            CASE WHEN mla.shortlist_rank IS NULL OR mla.shortlist_rank = 0 THEN 999999 ELSE mla.shortlist_rank END ASC
    """
    return frappe.db.sql(query, params, as_dict=True)

def get_final_allotment_data(filters):
    ml_filters = {
        "docstatus": ["<", 2],
        "status": ["!=", "Superseded"],
        "merit_processing_stage": "Final Allotment Ranking"
    }
    
    if filters.get("admission_cycle"):
        ml_filters["admission_cycle"] = filters.get("admission_cycle")
    elif filters.get("admission_year"):
        cycles = frappe.get_all("Admission Cycle", filters={"admission_year": filters.get("admission_year")}, pluck="name")
        if not cycles:
            return []
        ml_filters["admission_cycle"] = ["in", cycles]

    if filters.get("campus"):
        ml_filters["campus"] = filters.get("campus")

    raw_ml = frappe.get_all("Merit List",
        filters=ml_filters,
        fields=["name", "campus", "admission_cycle", "program_level", "program", "status", "modified"],
        order_by="modified desc"
    )

    if not raw_ml:
        return []

    # Dedup: keep the newest non-superseded merit list per (campus, cycle, program_level, program)
    ml_dedup = {}
    for ml in raw_ml:
        key = (ml.campus, ml.admission_cycle, ml.program_level, ml.get("program"))
        if key not in ml_dedup:
            ml_dedup[key] = ml

    target_mls = list(ml_dedup.values())
    if filters.get("program"):
        target_mls = [ml for ml in target_mls if not ml.get("program") or ml.get("program") == filters.get("program")]

    ml_names = [ml.name for ml in target_mls]
    if not ml_names:
        return []

    conditions = ["mla.parent IN %(ml_names)s", "mla.parentfield = 'merit_applicants'"]
    params = {"ml_names": ml_names}

    if filters.get("program"):
        conditions.append("mla.program = %(program)s")
        params["program"] = filters.get("program")

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            mla.overall_rank,
            mla.part_a_rank,
            mla.part_b_rank,
            mla.candidate_name,
            mla.applicant_id,
            mla.actual_category,
            mla.entrance_score,
            mla.interview_score,
            mla.total_score,
            mla.percentile_score,
            mla.shortlist_category as shortlisted_category,
            mla.status
        FROM
            `tabMerit List Applicant` mla
        JOIN
            `tabMerit List` ml ON mla.parent = ml.name
        WHERE
            {where_clause}
        ORDER BY
            CASE WHEN mla.overall_rank IS NULL OR mla.overall_rank = 0 THEN 999999 ELSE mla.overall_rank END ASC
    """
    return frappe.db.sql(query, params, as_dict=True)

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
