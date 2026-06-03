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
        {"label": "Last Transaction No", "fieldname": "reference_number", "fieldtype": "Data", "width": 160},
        {"label": "Last Transaction Date", "fieldname": "transaction_date", "fieldtype": "Date", "width": 140},
        {"label": "Payment Mode", "fieldname": "payment_mode", "fieldtype": "Data", "width": 120},
        {"label": "Bank Name", "fieldname": "bank_name", "fieldtype": "Data", "width": 130},
        {"label": "Account Number", "fieldname": "account_number", "fieldtype": "Data", "width": 140},
        {"label": "IFSC Code", "fieldname": "ifsc_code", "fieldtype": "Data", "width": 110},
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
            d.name, d.student, d.student_name, d.academic_year,
            d.fee_component, d.demand_type, d.demand_date, d.due_date,
            d.original_amount, d.waiver_amount, d.net_payable,
            d.paid_amount, d.outstanding_amount, d.status,
            fp.reference_number,
            fp.transaction_date,
            fp.payment_mode,
            fp.bank_name,
            fp.account_number,
            fp.ifsc_code
        FROM `tabFee Demand` d
        LEFT JOIN `tabFee Payment Demand Row` pdr ON pdr.fee_demand = d.name
        LEFT JOIN `tabFee Payment` fp ON fp.name = pdr.parent AND fp.docstatus = 1
        WHERE {conditions}
        ORDER BY d.demand_date DESC, d.student ASC
    """, filters, as_dict=True)

    return rows
