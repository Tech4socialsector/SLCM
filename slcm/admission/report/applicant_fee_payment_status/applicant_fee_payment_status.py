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


def _sum_receipts_by_offer(offer_letters: list[str]) -> dict[str, float]:
	if not offer_letters:
		return {}
	placeholders = ", ".join(["%s"] * len(offer_letters))
	rows = frappe.db.sql(
		f"""
		SELECT offer_letter, SUM(total_amount) AS total_amount
		FROM `tabApplicant Payment Receipt`
		WHERE docstatus = 1 AND offer_letter IN ({placeholders})
		GROUP BY offer_letter
		""",
		tuple(offer_letters),
		as_dict=True,
	)
	return {r.offer_letter: flt(r.total_amount) for r in rows}


def _sum_application_fee_receipts_by_applicant(applicants: list[str]) -> dict[str, float]:
	if not applicants:
		return {}
	placeholders = ", ".join(["%s"] * len(applicants))
	rows = frappe.db.sql(
		f"""
		SELECT applicant, SUM(total_amount) AS total_amount
		FROM `tabApplicant Payment Receipt`
		WHERE docstatus = 1
			AND applicant IN ({placeholders})
			AND IFNULL(offer_letter, '') = ''
		GROUP BY applicant
		""",
		tuple(applicants),
		as_dict=True,
	)
	return {r.applicant: flt(r.total_amount) for r in rows}


def get_data(filters: dict | None) -> list[dict]:
	"""Return data for the report based on filters."""
	filters = dict(filters or {})
	query_filters = {}

	ft = filters.get("fee_type")
	if ft is None:
		query_filters["fee_type"] = "Admission Fee"
	elif ft == "":
		pass
	else:
		query_filters["fee_type"] = ft

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
			"fee_type",
			"total_amount",
			"final_payable_amount",
			"fee_invoice",
			"offer_letter",
		],
		order_by="assignment_date asc",
	)

	invoice_names = list({r.fee_invoice for r in data if r.get("fee_invoice")})
	invoice_paid_map: dict[str, float] = {}
	if invoice_names:
		for inv in frappe.get_all(
			"Fee Invoice",
			filters={"name": ["in", invoice_names]},
			fields=["name", "paid_amount"],
		):
			invoice_paid_map[inv.name] = flt(inv.paid_amount)

	need_receipt_by_offer = [r for r in data if not r.get("fee_invoice") and r.get("offer_letter")]
	offer_letters = list({r.offer_letter for r in need_receipt_by_offer})
	offer_paid_map = _sum_receipts_by_offer(offer_letters)

	need_receipt_by_applicant = [
		r for r in data if not r.get("fee_invoice") and (r.get("fee_type") or "") == "Application Fee"
	]
	applicants = list({r.applicant for r in need_receipt_by_applicant})
	applicant_paid_map = _sum_application_fee_receipts_by_applicant(applicants)

	allocated_offer: dict[str, float] = {}
	allocated_applicant: dict[str, float] = {}

	ordered = sorted(data, key=lambda x: x.assignment_date or "")
	for row in ordered:
		total = flt(row.get("final_payable_amount") or 0)
		if row.get("fee_invoice"):
			paid_for_this = invoice_paid_map.get(row.fee_invoice, 0)
		elif (row.get("fee_type") or "") == "Application Fee":
			pool = applicant_paid_map.get(row.applicant, 0)
			available = max(0, pool - allocated_applicant.get(row.applicant, 0))
			paid_for_this = min(total, available)
			allocated_applicant[row.applicant] = allocated_applicant.get(row.applicant, 0) + paid_for_this
		elif row.get("offer_letter"):
			pool = offer_paid_map.get(row.offer_letter, 0)
			available = max(0, pool - allocated_offer.get(row.offer_letter, 0))
			paid_for_this = min(total, available)
			allocated_offer[row.offer_letter] = allocated_offer.get(row.offer_letter, 0) + paid_for_this
		else:
			paid_for_this = 0

		row["paid_amount"] = paid_for_this
		row["pending_amount"] = max(0, total - paid_for_this)

		if row["paid_amount"] >= total and row.status not in ["Paid", "Cancelled", "Converted"] and total > 0:
			row["status"] = "Paid"
		elif row["paid_amount"] > 0 and row["paid_amount"] < total and row.status not in (
			"Partially Paid",
			"Converted",
		):
			row["status"] = "Partially Paid"

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
