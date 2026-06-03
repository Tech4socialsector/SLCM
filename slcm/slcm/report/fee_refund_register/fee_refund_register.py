import frappe


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Refund No", "fieldname": "name", "fieldtype": "Link", "options": "Fee Refund", "width": 150},
        {"label": "Refund Date", "fieldname": "refund_date", "fieldtype": "Date", "width": 110},
        {"label": "Student ID", "fieldname": "student", "fieldtype": "Link", "options": "Student Master", "width": 140},
        {"label": "Student Name", "fieldname": "student_name", "fieldtype": "Data", "width": 160},
        {"label": "Fee Demand", "fieldname": "fee_demand", "fieldtype": "Link", "options": "Fee Demand", "width": 140},
        {"label": "Fee Component", "fieldname": "fee_component", "fieldtype": "Data", "width": 180},
        {"label": "Refund Type", "fieldname": "refund_type", "fieldtype": "Data", "width": 140},
        {"label": "Refund Amount (₹)", "fieldname": "refund_amount", "fieldtype": "Currency", "width": 150},
        {"label": "Refund Mode", "fieldname": "refund_mode", "fieldtype": "Data", "width": 120},
        {"label": "Transaction No (UTR)", "fieldname": "utr_number", "fieldtype": "Data", "width": 170},
        {"label": "Transaction Date", "fieldname": "transaction_date", "fieldtype": "Date", "width": 130},
        {"label": "Bank Name", "fieldname": "bank_name", "fieldtype": "Data", "width": 140},
        {"label": "Account Number", "fieldname": "account_number", "fieldtype": "Data", "width": 150},
        {"label": "IFSC Code", "fieldname": "ifsc_code", "fieldtype": "Data", "width": 120},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": "Approved By", "fieldname": "approved_by", "fieldtype": "Data", "width": 130},
        {"label": "Approved On", "fieldname": "approved_on", "fieldtype": "Date", "width": 110},
        {"label": "Reason", "fieldname": "reason", "fieldtype": "Data", "width": 200},
    ]


def get_data(filters):
    conditions = "r.docstatus != 2"

    if filters.get("from_date"):
        conditions += " AND r.refund_date >= %(from_date)s"

    if filters.get("to_date"):
        conditions += " AND r.refund_date <= %(to_date)s"

    if filters.get("student"):
        conditions += " AND r.student = %(student)s"

    if filters.get("refund_type"):
        conditions += " AND r.refund_type = %(refund_type)s"

    if filters.get("status"):
        conditions += " AND r.status = %(status)s"

    if filters.get("refund_mode"):
        conditions += " AND r.refund_mode = %(refund_mode)s"

    rows = frappe.db.sql(f"""
        SELECT
            r.name,
            r.refund_date,
            r.student,
            r.student_name,
            r.fee_demand,
            r.fee_component,
            r.refund_type,
            r.refund_amount,
            r.refund_mode,
            r.utr_number,
            r.transaction_date,
            r.bank_name,
            r.account_number,
            r.ifsc_code,
            r.status,
            r.approved_by,
            r.approved_on,
            r.reason
        FROM `tabFee Refund` r
        WHERE {conditions}
        ORDER BY r.refund_date DESC, r.name DESC
    """, filters, as_dict=True)

    return rows
