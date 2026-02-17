from __future__ import unicode_literals
import frappe

def execute(filters=None):
    columns, data = [], []
    
    columns = get_columns()
    data = get_data(filters)
    
    # Re-calculate ranks for combined view
    for i, row in enumerate(data):
        row[5] = i + 1 # Assign overall rank based on score sorting
        
    return columns, data

def get_columns():
    return [
        {
            "label": "Applicant",
            "fieldname": "applicant",
            "fieldtype": "Link",
            "options": "test Applicant",
            "width": 150
        },
        {
            "label": "Program",
            "fieldname": "program",
            "fieldtype": "Link",
            "options": "test Program",
            "width": 120
        },
        {
            "label": "Campus",
            "fieldname": "campus",
            "fieldtype": "Link",
            "options": "test Campus",
            "width": 120
        },
        {
            "label": "Category",
            "fieldname": "category",
            "fieldtype": "Select",
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
            mla.category,
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
        
    if filters.get("category"):
        query += " AND mla.category = %(category)s"
        
    query += " ORDER BY mla.total_score DESC"
    
    return frappe.db.sql(query, {
        "cycle": filters.get("admission_cycle"),
        "campus": filters.get("campus"),
        "program": filters.get("program"),
        "category": filters.get("category")
    }, as_list=1)
