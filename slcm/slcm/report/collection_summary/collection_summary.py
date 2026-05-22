import frappe
from frappe.utils import getdate


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Fee Component", "fieldname": "fee_component", "fieldtype": "Data", "width": 200},
        {"label": "Demand Type", "fieldname": "demand_type", "fieldtype": "Data", "width": 130},
        {"label": "Academic Year", "fieldname": "academic_year", "fieldtype": "Data", "width": 130},
        {"label": "Payment Mode", "fieldname": "payment_mode", "fieldtype": "Data", "width": 120},
        {"label": "No. of Receipts", "fieldname": "receipt_count", "fieldtype": "Int", "width": 120},
        {"label": "Total Collected (₹)", "fieldname": "total_collected", "fieldtype": "Currency", "width": 150},
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

    rows = frappe.db.sql(f"""
        SELECT
            d.fee_component,
            d.demand_type,
            r.academic_year,
            p.payment_mode,
            COUNT(DISTINCT r.name) AS receipt_count,
            SUM(r.amount) AS total_collected
        FROM `tabFee Receipt` r
        JOIN `tabFee Payment` p ON p.name = r.fee_payment
        JOIN `tabFee Payment Demand Row` pd ON pd.parent = p.name
        JOIN `tabFee Demand` d ON d.name = pd.fee_demand
        WHERE {conditions}
        GROUP BY d.fee_component, d.demand_type, r.academic_year, p.payment_mode
        ORDER BY r.academic_year DESC, total_collected DESC
    """, filters, as_dict=True)

    return rows
