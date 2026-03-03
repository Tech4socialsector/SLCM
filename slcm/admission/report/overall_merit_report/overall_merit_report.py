from __future__ import unicode_literals
import frappe

def execute(filters=None):
    columns, data = [], []
    
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data

def get_columns():
    return [
        {
            "label": "Applicant",
            "fieldname": "applicant",
            "fieldtype": "Link",
            "options": "Eligibility Result",
            "width": 150
        },
        {
            "label": "Applicant ID",
            "fieldname": "applicant_id",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Program",
            "fieldname": "program",
            "fieldtype": "Link",
            "options": "Program",
            "width": 120
        },
        {
            "label": "Campus",
            "fieldname": "campus",
            "fieldtype": "Link",
            "options": "Campus",
            "width": 120
        },
        {
            "label": "Category",
            "fieldname": "reservation_category",
            "fieldtype": "Link",
            "options": "Admission Category",
            "width": 100
        },
        {
            "label": "Total Score",
            "fieldname": "total_score",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": "Overall Rank",
            "fieldname": "overall_rank",
            "fieldtype": "Int",
            "width": 100
        }
    ]

def get_data(filters):
    query = """
        SELECT
            mla.applicant,
            aa.applicant_id,
            mla.program,
            ml.campus,
            mla.reservation_category,
            mla.total_score,
            mla.overall_rank
        FROM
            `tabMerit List Applicant` mla
        JOIN
            `tabMerit List` ml
        ON
            mla.parent = ml.name
        JOIN
            `tabEligibility Result` aa
        ON
            mla.applicant = aa.name
        WHERE
            ml.admission_cycle = %(cycle)s
            AND ml.campus = %(campus)s
    """
    
    if filters.get("program"):
        query += " AND mla.program = %(program)s"
        
    if filters.get("reservation_category"):
        query += " AND mla.reservation_category = %(reservation_category)s"
        
    # Standardize tie-breaking with merit_service.py
    query += " ORDER BY mla.total_score DESC, mla.entrance_score DESC, mla.hsc_percentage DESC, mla.interview_score DESC"
    
    return frappe.db.sql(query, {
        "cycle": filters.get("admission_cycle"),
        "campus": filters.get("campus"),
        "program": filters.get("program"),
        "reservation_category": filters.get("reservation_category")
    }, as_dict=True)

def get_chart_data(columns, data, filters):
    if not data:
        return None

    program_scores = {}
    program_counts = {}

    for d in data:
        prog = d.get("program")
        score = d.get("total_score") or 0
        program_scores[prog] = program_scores.get(prog, 0) + score
        program_counts[prog] = program_counts.get(prog, 0) + 1

    labels = sorted(program_scores.keys())
    values = [round(program_scores[l] / program_counts[l], 2) for l in labels]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": "Average Score", "values": values}]
        },
        "type": "bar",
        "colors": ["#7cd6fd"]
    }
