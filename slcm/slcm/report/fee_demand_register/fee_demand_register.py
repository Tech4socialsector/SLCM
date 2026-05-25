import frappe


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Demand ID", "fieldname": "name", "fieldtype": "Link", "options": "Fee Demand", "width": 140},
        {"label": "Student ID", "fieldname": "student", "fieldtype": "Link", "options": "Student Master", "width": 130},
        {"label": "Student Name", "fieldname": "student_name", "fieldtype": "Data", "width": 150},
        {"label": "Academic Year", "fieldname": "academic_year", "fieldtype": "Data", "width": 120},
        {"label": "Fee Component", "fieldname": "fee_component", "fieldtype": "Data", "width": 180},
        {"label": "Demand Type", "fieldname": "demand_type", "fieldtype": "Data", "width": 120},
        {"label": "Demand Date", "fieldname": "demand_date", "fieldtype": "Date", "width": 110},
        {"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 100},
        {"label": "Original Amount", "fieldname": "original_amount", "fieldtype": "Currency", "width": 130},
        {"label": "Waiver", "fieldname": "waiver_amount", "fieldtype": "Currency", "width": 100},
        {"label": "Net Payable", "fieldname": "net_payable", "fieldtype": "Currency", "width": 110},
        {"label": "Paid", "fieldname": "paid_amount", "fieldtype": "Currency", "width": 100},
        {"label": "Outstanding", "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 110},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
    ]


def get_data(filters):
    conditions = "1=1"

    if filters.get("academic_year"):
        conditions += " AND academic_year = %(academic_year)s"

    if filters.get("status"):
        conditions += " AND status = %(status)s"

    if filters.get("demand_type"):
        conditions += " AND demand_type = %(demand_type)s"

    if filters.get("from_date"):
        conditions += " AND demand_date >= %(from_date)s"

    if filters.get("to_date"):
        conditions += " AND demand_date <= %(to_date)s"

    if filters.get("student"):
        conditions += " AND student = %(student)s"

    rows = frappe.db.sql(f"""
        SELECT
            name, student, student_name, academic_year,
            fee_component, demand_type, demand_date, due_date,
            original_amount, waiver_amount, net_payable,
            paid_amount, outstanding_amount, status
        FROM `tabFee Demand`
        WHERE {conditions}
        ORDER BY demand_date DESC, student ASC
    """, filters, as_dict=True)

    return rows
