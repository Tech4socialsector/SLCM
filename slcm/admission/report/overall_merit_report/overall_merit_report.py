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
    if filters.get("merit_processing_stage") == "Part A Ranking":
        return get_part_a_data(filters)
    else:
        return get_final_allotment_data(filters)

def get_part_a_data(filters):
    conditions = []
    if filters.get("admission_cycle"):
        conditions.append("ml.admission_cycle = %(admission_cycle)s")
    if filters.get("campus"):
        conditions.append("ml.campus = %(campus)s")
    if filters.get("program"):
        conditions.append("mla.program = %(program)s")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            mla.shortlist_rank as overall_rank,
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
            mla.parentfield = 'shortlist_applicants' AND {where_clause}
        ORDER BY
            mla.shortlist_rank ASC
    """
    return frappe.db.sql(query, filters, as_dict=True)

def get_final_allotment_data(filters):
    conditions = []
    if filters.get("admission_cycle"):
        conditions.append("ml.admission_cycle = %(admission_cycle)s")
    if filters.get("campus"):
        conditions.append("ml.campus = %(campus)s")
    if filters.get("program"):
        conditions.append("mla.program = %(program)s")
    
    # Force Final Allotment stage if querying Merit List Applicant
    conditions.append("ml.merit_processing_stage = 'Final Allotment Ranking'")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            mla.overall_rank,
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
            mla.parentfield = 'merit_applicants' AND {where_clause}
        ORDER BY
            mla.overall_rank ASC
    """
    return frappe.db.sql(query, filters, as_dict=True)

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
