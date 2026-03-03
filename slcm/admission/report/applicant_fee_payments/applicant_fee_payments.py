import frappe
from frappe import _

def execute(filters: dict | None = None):
	columns = get_columns()
	data = get_data(filters)
	
	# Returning column and data, other parts handled via JS
	return columns, data, None, None, None

def get_columns() -> list[dict]:
	return [
		{
			"label": _("Receipt ID"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Applicant Payment Receipt",
			"width": 140
		},
		{
			"label": _("Applicant"),
			"fieldname": "applicant",
			"fieldtype": "Link",
			"options": "Applicant",
			"width": 120
		},
		{
			"label": _("Applicant Name"),
			"fieldname": "applicant_name",
			"fieldtype": "Data",
			"width": 180
		},
		{
			"label": _("Program"),
			"fieldname": "program",
			"fieldtype": "Link",
			"options": "Program",
			"width": 180
		},
		{
			"label": _("Campus"),
			"fieldname": "campus",
			"fieldtype": "Link",
			"options": "Campus",
			"width": 120
		},
		{
			"label": _("Payment Date"),
			"fieldname": "payment_date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": _("Payment Mode"),
			"fieldname": "payment_mode",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Transaction ID"),
			"fieldname": "transaction_id",
			"fieldtype": "Data",
			"width": 140
		},
		{
			"label": _("Amount"),
			"fieldname": "total_amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120
		},
		{
			"label": _("Currency"),
			"fieldname": "currency",
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1
		}
	]

def get_data(filters: dict | None) -> list[dict]:
	conditions = ""
	values = {}
	
	if filters:
		if filters.get("admission_year"):
			conditions += " AND academic_year = %(admission_year)s"
			values["admission_year"] = filters.get("admission_year")
		if filters.get("campus"):
			conditions += " AND campus = %(campus)s"
			values["campus"] = filters.get("campus")
		if filters.get("program"):
			conditions += " AND program = %(program)s"
			values["program"] = filters.get("program")
		if filters.get("payment_mode"):
			conditions += " AND payment_mode = %(payment_mode)s"
			values["payment_mode"] = filters.get("payment_mode")
		if filters.get("from_date"):
			conditions += " AND payment_date >= %(from_date)s"
			values["from_date"] = filters.get("from_date")
		if filters.get("to_date"):
			conditions += " AND payment_date <= %(to_date)s"
			values["to_date"] = filters.get("to_date")

	data = frappe.db.sql(f"""
		SELECT 
			name, applicant, applicant_name, program, academic_year,
			campus, payment_date, payment_mode, transaction_id, 
			total_amount, currency
		FROM `tabApplicant Payment Receipt`
		WHERE docstatus = 1 {conditions}
		ORDER BY payment_date DESC, name DESC
	""", values, as_dict=1)
	
	return data
