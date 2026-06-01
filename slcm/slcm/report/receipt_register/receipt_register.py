import frappe


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Receipt No", "fieldname": "name", "fieldtype": "Link", "options": "Fee Receipt", "width": 150},
        {"label": "Receipt Date", "fieldname": "receipt_date", "fieldtype": "Date", "width": 110},
        {"label": "Student ID", "fieldname": "student", "fieldtype": "Link", "options": "Student Master", "width": 130},
        {"label": "Student Name", "fieldname": "student_name", "fieldtype": "Data", "width": 150},
        {"label": "Academic Year", "fieldname": "academic_year", "fieldtype": "Data", "width": 120},
        {"label": "Payment Mode", "fieldname": "payment_mode", "fieldtype": "Data", "width": 120},
        {"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 120},
        {"label": "Fee Payment", "fieldname": "fee_payment", "fieldtype": "Link", "options": "Fee Payment", "width": 140},
    ]


def get_data(filters):
    conditions = "r.docstatus = 1"

    if filters.get("from_date"):
        conditions += " AND r.receipt_date >= %(from_date)s"

    if filters.get("to_date"):
        conditions += " AND r.receipt_date <= %(to_date)s"

    if filters.get("academic_year"):
        conditions += " AND r.academic_year = %(academic_year)s"

    if filters.get("payment_mode"):
        conditions += " AND p.payment_mode = %(payment_mode)s"

    if filters.get("student"):
        conditions += " AND r.student = %(student)s"

    rows = frappe.db.sql(f"""
        SELECT
            r.name,
            r.receipt_date,
            r.student,
            r.student_name,
            r.academic_year,
            p.payment_mode,
            r.amount,
            r.fee_payment
        FROM `tabFee Receipt` r
        LEFT JOIN `tabFee Payment` p ON p.name = r.fee_payment
        WHERE {conditions}
        ORDER BY r.receipt_date DESC, r.name DESC
    """, filters, as_dict=True)

    return rows
