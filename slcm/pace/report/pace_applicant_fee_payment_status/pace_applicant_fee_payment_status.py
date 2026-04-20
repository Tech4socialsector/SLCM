import frappe
from frappe import _
from frappe.utils import flt


def execute(filters: dict | None = None):
	"""Return columns and data for the report."""
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	report_summary = get_report_summary(data)

	return columns, data, None, chart, report_summary


def get_columns() -> list[dict]:
	"""Return columns for the report."""
	return [
		{
			"label": _("ID"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "PACE Applicant Fee Assignment",
			"width": 140
		},
		{
			"label": _("Application"),
			"fieldname": "applicant",
			"fieldtype": "Link",
			"options": "PACE Application",
			"width": 140
		},
		{
			"label": _("Applicant Name"),
			"fieldname": "applicant_name",
			"fieldtype": "Data",
			"width": 180
		},
		{
			"label": _("Academic Year"),
			"fieldname": "academic_year",
			"fieldtype": "Link",
			"options": "Academic Year",
			"width": 120
		},
		{
			"label": _("Programme"),
			"fieldname": "program",
			"fieldtype": "Link",
			"options": "PACE Programme",
			"width": 180
		},
		{
			"label": _("Assignment Date"),
			"fieldname": "assignment_date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100
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
		}
	]


def get_data(filters: dict | None) -> list[dict]:
	"""Return data for the report based on filters."""
	filters = dict(filters or {})
	query_filters = {}

	if filters.get("fee_type"):
		query_filters["fee_type"] = filters.get("fee_type")
	if filters.get("academic_year"):
		query_filters["academic_year"] = filters.get("academic_year")
	if filters.get("program"):
		query_filters["program"] = filters.get("program")
	if filters.get("status"):
		query_filters["status"] = filters.get("status")

	if filters.get("from_date") and filters.get("to_date"):
		query_filters["assignment_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
	elif filters.get("from_date"):
		query_filters["assignment_date"] = [">=", filters.get("from_date")]
	elif filters.get("to_date"):
		query_filters["assignment_date"] = ["<=", filters.get("to_date")]

	data = frappe.get_all(
		"PACE Applicant Fee Assignment",
		filters=query_filters,
		fields=[
			"name",
			"applicant",
			"applicant_name",
			"academic_year",
			"program",
			"assignment_date",
			"status",
			"final_payable_amount",
		],
		order_by="assignment_date desc",
	)

	if not data:
		return []

	# Fetch paid amounts from PACE Receipt
	assignment_names = [r.name for r in data]
	receipt_data = frappe.get_all(
		"PACE Receipt",
		filters={"fee_assignment": ["in", assignment_names], "docstatus": ["!=", 2]},
		fields=["fee_assignment", "amount"],
	)

	paid_map = {}
	for rd in receipt_data:
		paid_map[rd.fee_assignment] = paid_map.get(rd.fee_assignment, 0) + flt(rd.amount)

	for row in data:
		payable = flt(row.get("final_payable_amount") or 0)
		paid = flt(paid_map.get(row.name, 0))
		row["paid_amount"] = paid
		row["pending_amount"] = max(0, payable - paid)

		# Sync status for display if paid
		if paid >= payable and payable > 0 and row.status not in ["Paid", "Cancelled", "Converted", "Enrolled"]:
			row["status"] = _("Paid")
		elif 0 < paid < payable and row.status not in ["Partially Paid", "Cancelled", "Converted", "Enrolled"]:
			row["status"] = _("Partially Paid")

	return data


def get_chart(data: list[dict]) -> dict:
	"""Return chart data showing Total Paid vs Total Pending."""
	if not data:
		return {}

	total_paid = sum(flt(row.get("paid_amount") or 0) for row in data)
	total_pending = sum(flt(row.get("pending_amount") or 0) for row in data)

	return {
		"data": {
			"labels": [_("Paid"), _("Pending")],
			"datasets": [{"values": [total_paid, total_pending]}],
		},
		"type": "donut",
		"height": 200,
		"colors": ["#28a745", "#ff5858"]
	}


def get_report_summary(data: list[dict]) -> list[dict]:
	"""Return report summary cards."""
	if not data:
		return []

	total_count = len(data)
	total_amount = sum(flt(row.get("final_payable_amount") or 0) for row in data)
	paid_amount = sum(flt(row.get("paid_amount") or 0) for row in data)
	pending_amount = sum(flt(row.get("pending_amount") or 0) for row in data)

	return [
		{
			"value": total_count,
			"indicator": "Blue",
			"label": _("Total Assignments"),
			"datatype": "Int",
		},
		{
			"value": total_amount,
			"indicator": "Orange",
			"label": _("Total Amount Assigned"),
			"datatype": "Currency",
		},
		{
			"value": paid_amount,
			"indicator": "Green",
			"label": _("Total Amount Paid"),
			"datatype": "Currency",
		},
		{
			"value": total_amount - paid_amount, # Show true pending even if negative overflow
			"indicator": "Red",
			"label": _("Pending Amount"),
			"datatype": "Currency",
		}
	]
