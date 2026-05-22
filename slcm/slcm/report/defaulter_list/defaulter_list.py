import frappe
from frappe.utils import today, getdate, date_diff


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Student ID", "fieldname": "student", "fieldtype": "Link", "options": "Student Master", "width": 140},
        {"label": "Student Name", "fieldname": "student_name", "fieldtype": "Data", "width": 160},
        {"label": "Demand ID", "fieldname": "name", "fieldtype": "Link", "options": "Fee Demand", "width": 140},
        {"label": "Fee Component", "fieldname": "fee_component", "fieldtype": "Data", "width": 180},
        {"label": "Demand Type", "fieldname": "demand_type", "fieldtype": "Data", "width": 120},
        {"label": "Academic Year", "fieldname": "academic_year", "fieldtype": "Data", "width": 120},
        {"label": "Original Amount", "fieldname": "original_amount", "fieldtype": "Currency", "width": 130},
        {"label": "Outstanding", "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120},
        {"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 100},
        {"label": "Days Overdue", "fieldname": "days_overdue", "fieldtype": "Int", "width": 110},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 90},
    ]


def get_data(filters):
    conditions = "d.status IN ('Pending', 'Overdue', 'Partially Paid')"

    if filters.get("academic_year"):
        conditions += f" AND d.academic_year = %(academic_year)s"

    if filters.get("demand_type"):
        conditions += f" AND d.demand_type = %(demand_type)s"

    if filters.get("student"):
        conditions += f" AND d.student = %(student)s"

    as_of = filters.get("as_of_date") or today()
    conditions += f" AND d.due_date < %(as_of)s"
    filters["as_of"] = as_of

    rows = frappe.db.sql(f"""
        SELECT
            d.name,
            d.student,
            d.student_name,
            d.fee_component,
            d.demand_type,
            d.academic_year,
            d.original_amount,
            d.outstanding_amount,
            d.due_date,
            d.status
        FROM `tabFee Demand` d
        WHERE {conditions}
        ORDER BY d.due_date ASC, d.student ASC
    """, filters, as_dict=True)

    for row in rows:
        row["days_overdue"] = date_diff(today(), row["due_date"]) if row["due_date"] else 0

    return rows
