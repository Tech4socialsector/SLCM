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
        {"label": _("Karnataka Student"), "fieldname": "compartmentalized_category", "fieldtype": "Data", "width": 130},
        {"label": _("Horizontal"), "fieldname": "horizontal_categories", "fieldtype": "Data", "width": 150},
        {"label": _("Allocated Category"), "fieldname": "allocated_category", "fieldtype": "Data", "width": 150},
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
            er.percentile_score,
            mla.compartmentalized_category,
            mla.horizontal_categories,
            mla.shortlist_category as allocated_category,
            mla.shortlist_status as status
        FROM
            `tabShortlisting Merit Candidate` mla
        JOIN
            `tabShortlisting Merit List` ml ON mla.parent = ml.name
        LEFT JOIN
            `tabEligibility Result` er ON mla.applicant_id = er.applicant_id
        WHERE
            {where_clause}
        ORDER BY
            CASE 
                WHEN mla.shortlist_status = 'Shortlisted' THEN 1 
                ELSE 2 
            END,
            mla.shortlist_category ASC,
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
            mla.compartmentalized_category,
            mla.horizontal_categories,
            mla.allocated_category,
            mla.status
        FROM
            `tabMerit List Applicant` mla
        JOIN
            `tabMerit List` ml ON mla.parent = ml.name
        WHERE
            {where_clause}
        ORDER BY
            CASE 
                WHEN mla.status = 'Selected' THEN 1 
                WHEN mla.status = 'Waitlisted' THEN 2 
                ELSE 3 
            END,
            mla.allocated_category ASC,
            mla.overall_rank ASC
    """
    return frappe.db.sql(query, filters, as_dict=True)

def get_chart(data):
    if not data:
        return None

    # Chart showing breakdown of Selected/Shortlisted candidates by Allocated Category
    category_counts = {}
    for d in data:
        if d.status in ["Selected", "Shortlisted"]:
            cat = d.allocated_category or "Unallocated"
            # Simplify category name for chart if it's too long
            display_cat = cat.replace("Karnataka", "KA").replace("Women", "W").replace("PWD", "P")
            category_counts[display_cat] = category_counts.get(display_cat, 0) + 1

    if not category_counts:
        return None

    labels = sorted(category_counts.keys())
    values = [category_counts[l] for l in labels]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": _("Selected/Shortlisted"), "values": values}]
        },
        "type": "bar",
        "height": 300,
        "colors": ["#7cd6fd"]
    }

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
