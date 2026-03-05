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
			"options": "Applicant Fee Assignment",
			"width": 140
		},
		{
			"label": _("Applicant ID"),
			"fieldname": "applicant",
			"fieldtype": "Link",
			"options": "Applicant",
			"width": 140
		},
		{
			"label": _("Candidate Name"),
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
			"label": _("Program"),
			"fieldname": "program",
			"fieldtype": "Link",
			"options": "Program",
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
		},
		{
			"label": _("Fee Invoice"),
			"fieldname": "fee_invoice",
			"fieldtype": "Link",
			"options": "Fee Invoice",
			"width": 140
		}
	]


def get_data(filters: dict | None) -> list[dict]:
	"""Return data for the report based on filters."""
	query_filters = {}

	if filters.get("academic_year"):
		query_filters["academic_year"] = filters.get("academic_year")
	if filters.get("program"):
		query_filters["program"] = filters.get("program")
	if filters.get("status"):
		query_filters["status"] = filters.get("status")
	if filters.get("applicant"):
		query_filters["applicant"] = filters.get("applicant")

	if filters.get("from_date") and filters.get("to_date"):
		query_filters["assignment_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
	elif filters.get("from_date"):
		query_filters["assignment_date"] = [">=", filters.get("from_date")]
	elif filters.get("to_date"):
		query_filters["assignment_date"] = ["<=", filters.get("to_date")]

	data = frappe.get_all(
		"Applicant Fee Assignment",
		filters=query_filters,
		fields=[
			"name",
			"applicant",
			"applicant_name",
			"academic_year",
			"program",
			"assignment_date",
			"status",
			"total_amount",
			"final_payable_amount",
			"fee_invoice",
			"offer_letter"
		],
		order_by="assignment_date asc"
	)

	# Get all unique offer letters to fetch their total receipts
	offer_letters = list(set(row.offer_letter for row in data if row.offer_letter))
	offer_paid_map = {}
	if offer_letters:
		receipt_data = frappe.get_all(
			"Applicant Payment Receipt",
			filters={"offer_letter": ["in", offer_letters], "docstatus": 1},
			fields=["offer_letter", {"SUM": "total_amount"}],
			group_by="offer_letter"
		)
		for r in receipt_data:
			offer_paid_map[r.offer_letter] = flt(r.total_amount)

	# Keep track of how much of each offer's payment has been allocated
	allocated_paid = {}

	# Calculate paid and pending amounts for each assignment
	for row in data:
		total = flt(row.get("final_payable_amount") or 0)
		offer_total_paid = offer_paid_map.get(row.offer_letter, 0)
		
		# Remaining available paid amount for this offer
		available_paid = max(0, offer_total_paid - allocated_paid.get(row.offer_letter, 0))
		
		# Allocate to this assignment up to its total
		paid_for_this = min(total, available_paid)
		row["paid_amount"] = paid_for_this
		row["pending_amount"] = max(0, total - paid_for_this)
		
		# Update allocated record
		allocated_paid[row.offer_letter] = allocated_paid.get(row.offer_letter, 0) + paid_for_this
		
		# Sync display status if inconsistent
		if row["paid_amount"] >= total and row.status not in ["Paid", "Cancelled", "Converted"] and total > 0:
			row["status"] = "Paid"
		elif row["paid_amount"] > 0 and row["paid_amount"] < total and row.status != "Partially Paid":
			row["status"] = "Partially Paid"

	# Sort back to descending date for display
	data.sort(key=lambda x: x.assignment_date or "", reverse=True)
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
		"height": 300,
		"colors": ["#28a745", "#ff5858"]
	}


def get_report_summary(data: list[dict]) -> list[dict]:
	"""Return report summary cards."""
	if not data:
		return []

	total_count = len(data)
	total_amount = sum(float(row.get("final_payable_amount") or 0) for row in data)
	paid_amount = sum(float(row.get("paid_amount") or 0) for row in data)
	pending_amount = sum(float(row.get("pending_amount") or 0) for row in data)

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
			"value": pending_amount,
			"indicator": "Red",
			"label": _("Pending Amount"),
			"datatype": "Currency",
		}
	]
