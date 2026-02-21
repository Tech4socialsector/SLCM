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
            "options": "Admission Result",
            "width": 150
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
            "fieldname": "rank",
            "fieldtype": "Int",
            "width": 100
        }
    ]

def get_data(filters):
    query = """
        SELECT
            mla.applicant,
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
        WHERE
            ml.admission_cycle = %(cycle)s
            AND ml.campus = %(campus)s
    """
    
    if filters.get("program"):
        query += " AND mla.program = %(program)s"
        
    if filters.get("reservation_category"):
        query += " AND mla.reservation_category = %(reservation_category)s"
        
    # Standardize tie-breaking with merit_service.py
    query += " ORDER BY mla.total_score DESC, mla.entrance_percentage DESC, mla.hsc_percentage DESC, mla.interview_percentage DESC"
    
    return frappe.db.sql(query, {
        "cycle": filters.get("admission_cycle"),
        "campus": filters.get("campus"),
        "program": filters.get("program"),
        "reservation_category": filters.get("reservation_category")
    }, as_list=1)
