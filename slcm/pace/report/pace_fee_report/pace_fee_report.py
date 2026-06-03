import frappe
from frappe import _
from frappe.utils import flt


def execute(filters: dict | None = None):
	"""Return columns and data for the report."""
	columns = get_columns()
	data = get_data(filters)
	report_summary = get_report_summary(data)

	return columns, data, None, None, report_summary


def get_columns() -> list[dict]:
	"""Return columns for the report."""
	return [
		{
			"label": _("Fee Reference Number"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "PACE Applicant Fee Assignment",
			"width": 140
		},
		{
			"label": _("Applicant ID"),
			"fieldname": "applicant",
			"fieldtype": "Link",
			"options": "PACE Application",
			"width": 140
		},
		{
			"label": _("Applicant Name"),
			"fieldname": "applicant_name",
			"fieldtype": "Data",
			"width": 160
		},
		{
			"label": _("Email Address"),
			"fieldname": "email_address",
			"fieldtype": "Data",
			"width": 180
		},
		{
			"label": _("Mobile Number"),
			"fieldname": "mobile_number",
			"fieldtype": "Data",
			"width": 130
		},
		{
			"label": _("Programme"),
			"fieldname": "program",
			"fieldtype": "Link",
			"options": "PACE Programme",
			"width": 160
		},
		{
			"label": _("Academic Year"),
			"fieldname": "academic_year",
			"fieldtype": "Link",
			"options": "Academic Year",
			"width": 120
		},
		{
			"label": _("Fee Type"),
			"fieldname": "fee_type",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("Assignment Date"),
			"fieldname": "assignment_date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": _("Payable Amount"),
			"fieldname": "final_payable_amount",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("Paid Amount"),
			"fieldname": "paid_amount",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("Pending Amount"),
			"fieldname": "pending_amount",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("Payment Date"),
			"fieldname": "payment_date",
			"fieldtype": "Datetime",
			"width": 150
		},
		{
			"label": _("Transaction ID"),
			"fieldname": "transaction_id",
			"fieldtype": "Data",
			"width": 180
		}
	]


def get_data(filters: dict | None) -> list[dict]:
	"""Return data for the report based on filters."""
	filters = dict(filters or {})
	query_filters = {}

	if filters.get("program"):
		query_filters["program"] = filters.get("program")
	if filters.get("fee_type"):
		query_filters["fee_type"] = filters.get("fee_type")
	if filters.get("academic_year"):
		query_filters["academic_year"] = filters.get("academic_year")

	if filters.get("from_date") and filters.get("to_date"):
		query_filters["assignment_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
	elif filters.get("from_date"):
		query_filters["assignment_date"] = [">=", filters.get("from_date")]
	elif filters.get("to_date"):
		query_filters["assignment_date"] = ["<=", filters.get("to_date")]

	assignments = frappe.get_all(
		"PACE Applicant Fee Assignment",
		filters=query_filters,
		fields=[
			"name",
			"applicant",
			"applicant_name",
			"academic_year",
			"program",
			"fee_type",
			"status",
			"assignment_date",
			"final_payable_amount",
		],
		order_by="assignment_date desc"
	)

	if not assignments:
		return []

	# Get applicant email and mobile from PACE Application
	applicant_ids = [a.applicant for a in assignments if a.applicant]
	app_details = {}
	if applicant_ids:
		apps = frappe.get_all(
			"PACE Application",
			filters={"name": ["in", applicant_ids]},
			fields=["name", "email_address", "mobile_number"]
		)
		for app in apps:
			app_details[app.name] = app

	# Fetch receipts for paid amounts
	assignment_names = [a.name for a in assignments]
	receipts = {}
	if assignment_names:
		receipt_records = frappe.get_all(
			"PACE Receipt",
			filters={"fee_assignment": ["in", assignment_names], "docstatus": ["!=", 2]},
			fields=["fee_assignment", "amount", "payment_date", "transaction_id"],
			order_by="payment_date asc"
		)
		for r in receipt_records:
			fa = r.fee_assignment
			if fa not in receipts:
				receipts[fa] = {
					"paid_amount": 0.0,
					"payment_dates": [],
					"transaction_ids": []
				}
			receipts[fa]["paid_amount"] += flt(r.amount)
			if r.payment_date:
				receipts[fa]["payment_dates"].append(r.payment_date)
			if r.transaction_id:
				receipts[fa]["transaction_ids"].append(r.transaction_id)

	data = []
	for row in assignments:
		app_info = app_details.get(row.applicant) or {}
		row["email_address"] = app_info.get("email_address")
		row["mobile_number"] = app_info.get("mobile_number")

		receipt_info = receipts.get(row.name) or {}
		paid = flt(receipt_info.get("paid_amount", 0.0))
		row["paid_amount"] = paid
		
		payable = flt(row.final_payable_amount or 0.0)
		row["pending_amount"] = max(0.0, payable - paid)

		dates = receipt_info.get("payment_dates", [])
		t_ids = receipt_info.get("transaction_ids", [])
		
		row["payment_date"] = dates[-1] if dates else None
		row["transaction_id"] = ", ".join(t_ids) if t_ids else None

		# Map display status to Assigned, Paid, or Pending
		if paid >= payable and payable > 0:
			row["status"] = _("Paid")
		elif 0 < paid < payable:
			row["status"] = _("Pending")
		else:
			row["status"] = _("Assigned")

		data.append(row)

	# Filter by dynamic display status in Python if requested
	status_filter = filters.get("status")
	if status_filter:
		data = [row for row in data if row["status"] == status_filter]

	return data


def get_report_summary(data: list[dict]) -> list[dict]:
	"""Return report summary cards."""
	if not data:
		return []

	total_count = len(data)
	total_payable = sum(flt(row.get("final_payable_amount") or 0) for row in data)
	total_paid = sum(flt(row.get("paid_amount") or 0) for row in data)
	total_pending = sum(flt(row.get("pending_amount") or 0) for row in data)

	return [
		{
			"value": total_count,
			"indicator": "Blue",
			"label": _("Total Assignments"),
			"datatype": "Int",
		},
		{
			"value": total_payable,
			"indicator": "Orange",
			"label": _("Total Assigned Amount"),
			"datatype": "Currency",
		},
		{
			"value": total_paid,
			"indicator": "Green",
			"label": _("Total Paid Amount"),
			"datatype": "Currency",
		},
		{
			"value": total_pending,
			"indicator": "Red",
			"label": _("Total Pending Amount"),
			"datatype": "Currency",
		}
	]
