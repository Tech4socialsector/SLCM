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
			"label": _("Applicant"),
			"fieldname": "applicant",
			"fieldtype": "Link",
			"options": "Applicant",
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
			"label": _("Total Amount"),
			"fieldname": "total_amount",
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
			"fee_invoice",
			"offer_letter"
		],
		order_by="assignment_date desc"
	)

	# Calculate paid and pending amounts from receipts
	for row in data:
		total = flt(row.get("total_amount") or 0)
		
		# Sum all submitted receipts for this offer/assignment
		paid = flt(frappe.db.sql("""
			SELECT SUM(total_amount) 
			FROM `tabApplicant Payment Receipt` 
			WHERE offer_letter = %s AND docstatus = 1
		""", (row.offer_letter,))[0][0] or 0)
		
		row["paid_amount"] = paid
		row["pending_amount"] = max(0, total - paid)
		
		# Sync display status if inconsistent
		if paid >= total and row.status != "Paid" and total > 0:
			row["status"] = "Paid"
		elif paid > 0 and paid < total and row.status != "Partially Paid":
			row["status"] = "Partially Paid"

	return data


def get_chart(data: list[dict]) -> dict:
	"""Return chart data showing distribution by status."""
	if not data:
		return {}

	status_counts = {}
	for row in data:
		status = row.get("status") or _("Not Specified")
		status_counts[status] = status_counts.get(status, 0) + 1

	return {
		"data": {
			"labels": list(status_counts.keys()),
			"datasets": [{"values": list(status_counts.values())}],
		},
		"type": "donut",
		"colors": ["#7cd6fd", "#743ee2", "#ff5858", "#ffa00a", "#17a2b8", "#28a745"]
	}


def get_report_summary(data: list[dict]) -> list[dict]:
	"""Return report summary cards."""
	if not data:
		return []

	total_count = len(data)
	total_amount = sum(float(row.get("total_amount") or 0) for row in data)
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
