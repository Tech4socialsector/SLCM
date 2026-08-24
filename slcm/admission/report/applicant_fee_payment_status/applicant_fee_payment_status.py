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
			"label": _("Admission Year"),
			"fieldname": "admission_year",
			"fieldtype": "Link",
			"options": "Admission Year",
			"width": 120
		},
		{
			"label": _("Applicant ID"),
			"fieldname": "applicant",
			"fieldtype": "Link",
			"options": "Applicant",
			"width": 140
		},
		{
			"label": _("Email Address"),
			"fieldname": "email",
			"fieldtype": "Data",
			"width": 180
		},
		{
			"label": _("Mobile Number"),
			"fieldname": "mobile_number",
			"fieldtype": "Data",
			"width": 140
		},
		{
			"label": _("Candidate Name"),
			"fieldname": "applicant_name",
			"fieldtype": "Data",
			"width": 180
		},

		{
			"label": _("Programme"),
			"fieldname": "program",
			"fieldtype": "Link",
			"options": "Programme",
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
			"label": _("Fee Type"),
			"fieldname": "fee_type",
			"fieldtype": "Data",
			"width": 140
		},
		{
			"label": _("Payment Date"),
			"fieldname": "payment_date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": _("Transaction ID"),
			"fieldname": "transaction_id",
			"fieldtype": "Data",
			"width": 160
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

def _sum_receipts_by_offer(offer_letters: list[str]) -> dict[str, float]:
	if not offer_letters:
		return {}
	placeholders = ", ".join(["%s"] * len(offer_letters))
	legacy_rows = frappe.db.sql(
		f"""
		SELECT offer_letter as ref_name, SUM(total_amount) AS total_amount, transaction_id, payment_date
		FROM `tabApplicant Payment Receipt`
		WHERE docstatus = 1 AND offer_letter IN ({placeholders})
		GROUP BY offer_letter, transaction_id, payment_date
		""",
		tuple(offer_letters),
		as_dict=True,
	)

	pr_rows = frappe.db.sql(
		f"""
		SELECT reference_name as ref_name, SUM(amount) AS total_amount, transaction_id, DATE(creation) as payment_date
		FROM `tabPayment Request`
		WHERE status = 'Paid' AND reference_doctype = 'Offer Letter' AND reference_name IN ({placeholders})
		GROUP BY reference_name, transaction_id, DATE(creation)
		""",
		tuple(offer_letters),
		as_dict=True,
	)

	result = {}
	for r in legacy_rows + pr_rows:
		if r.ref_name not in result:
			result[r.ref_name] = {"total_amount": 0.0, "transaction_ids": [], "payment_dates": []}
		result[r.ref_name]["total_amount"] += flt(r.total_amount)
		if r.get("transaction_id"):
			result[r.ref_name]["transaction_ids"].append(str(r.transaction_id))
		if r.get("payment_date"):
			result[r.ref_name]["payment_dates"].append(r.payment_date)
	return result


def _sum_application_fee_receipts_by_applicant(applicants: list[str]) -> dict[str, float]:
	if not applicants:
		return {}
	placeholders = ", ".join(["%s"] * len(applicants))
	legacy_rows = frappe.db.sql(
		f"""
		SELECT applicant as ref_name, SUM(total_amount) AS total_amount, transaction_id, payment_date
		FROM `tabApplicant Payment Receipt`
		WHERE docstatus = 1
			AND applicant IN ({placeholders})
			AND IFNULL(offer_letter, '') = ''
		GROUP BY applicant, transaction_id, payment_date
		""",
		tuple(applicants),
		as_dict=True,
	)

	pr_rows = frappe.db.sql(
		f"""
		SELECT reference_name as ref_name, SUM(amount) AS total_amount, transaction_id, DATE(creation) as payment_date
		FROM `tabPayment Request`
		WHERE status = 'Paid' AND reference_doctype = 'Applicant' AND reference_name IN ({placeholders})
		GROUP BY reference_name, transaction_id, DATE(creation)
		""",
		tuple(applicants),
		as_dict=True,
	)

	result = {}
	for r in legacy_rows + pr_rows:
		if r.ref_name not in result:
			result[r.ref_name] = {"total_amount": 0.0, "transaction_ids": [], "payment_dates": []}
		result[r.ref_name]["total_amount"] += flt(r.total_amount)
		if r.get("transaction_id"):
			result[r.ref_name]["transaction_ids"].append(str(r.transaction_id))
		if r.get("payment_date"):
			result[r.ref_name]["payment_dates"].append(r.payment_date)
	return result


def get_data(filters: dict | None) -> list[dict]:
	"""Return data for the report based on filters."""
	filters = dict(filters or {})
	query_filters = {}

	ft = filters.get("fee_type")
	if ft:
		query_filters["fee_type"] = ft

	if filters.get("admission_year"):
		query_filters["applicant.admission_year"] = filters.get("admission_year")
	if filters.get("program"):
		query_filters["program"] = filters.get("program")
	req_status = filters.get("status")
	if req_status:
		if req_status == "Paid":
			query_filters["status"] = ["in", ["Paid", "Converted"]]
		elif req_status == "Pending":
			query_filters["status"] = "Assigned"
		elif req_status == "Partially Paid":
			query_filters["status"] = "Partially Paid"
	else:
		query_filters["status"] = ["not in", ["Draft", "Cancelled"]]

	if filters.get("applicant"):
		query_filters["applicant"] = filters.get("applicant")

	# Date filters are applied IN MEMORY after global payment allocation
	# to avoid corrupting the payment pool math.

	data = frappe.get_all(
		"Applicant Fee Assignment",
		filters=query_filters,
		fields=[
			"name",
			"applicant",
			"applicant.admission_year",
			"applicant.email",
			"applicant.mobile_number",
			"applicant_name",
			"program",
			"assignment_date",
			"status",
			"fee_type",
			"total_amount",
			"final_payable_amount",
			"fee_invoice",
			"offer_letter",
			"payment_date",
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

	import datetime
	ordered = sorted(data, key=lambda x: x.assignment_date or datetime.date.min)
	for row in ordered:
		total = flt(row.get("final_payable_amount") or 0)
		pool_dict = {}
		
		if row.get("fee_invoice"):
			paid_for_this = invoice_paid_map.get(row.fee_invoice, 0)
		elif (row.get("fee_type") or "") == "Application Fee":
			pool_dict = applicant_paid_map.get(row.applicant, {})
			pool = pool_dict.get("total_amount", 0)
			available = max(0, pool - allocated_applicant.get(row.applicant, 0))
			paid_for_this = min(total, available)
			allocated_applicant[row.applicant] = allocated_applicant.get(row.applicant, 0) + paid_for_this
		elif row.get("offer_letter"):
			pool_dict = offer_paid_map.get(row.offer_letter, {})
			pool = pool_dict.get("total_amount", 0)
			available = max(0, pool - allocated_offer.get(row.offer_letter, 0))
			paid_for_this = min(total, available)
			allocated_offer[row.offer_letter] = allocated_offer.get(row.offer_letter, 0) + paid_for_this
		else:
			paid_for_this = 0

		row["paid_amount"] = paid_for_this
		row["pending_amount"] = max(0, total - paid_for_this)
		
		if pool_dict.get("transaction_ids"):
			row["transaction_id"] = ", ".join(list(set(pool_dict["transaction_ids"])))
		
		if not row.get("payment_date") and pool_dict.get("payment_dates"):
			row["payment_date"] = max(pool_dict["payment_dates"])

		if row["paid_amount"] >= total and row.status not in ["Paid", "Cancelled", "Converted"] and total > 0:
			row["status"] = "Paid"
		elif row["paid_amount"] > 0 and row["paid_amount"] < total and row.status not in (
			"Partially Paid",
			"Converted",
		):
			row["status"] = "Partially Paid"

		if row["status"] == "Converted":
			row["status"] = "Paid"
		elif row["status"] == "Assigned":
			row["status"] = "Pending"

	# Now apply date filters in memory
	filtered_data = []
	from_date_obj = None
	to_date_obj = None
	
	if filters.get("from_date"):
		from_date_obj = frappe.utils.getdate(filters.get("from_date"))
	if filters.get("to_date"):
		to_date_obj = frappe.utils.getdate(filters.get("to_date"))

	for row in data:
		dt = row.get("assignment_date")
		if not dt:
			if from_date_obj or to_date_obj:
				continue
		else:
			if from_date_obj and dt < from_date_obj:
				continue
			if to_date_obj and dt > to_date_obj:
				continue
		filtered_data.append(row)

	filtered_data.sort(key=lambda x: x.assignment_date or datetime.date.min, reverse=True)
	return filtered_data


def get_chart(data: list[dict]) -> dict:
	"""Return chart data showing Total Paid vs Total Pending."""
	if not data:
		return None

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
			"label": _("Total No Of Invoice"),
			"datatype": "Int",
		},
		{
			"value": total_amount,
			"indicator": "Orange",
			"label": _("Total Invoice Amount"),
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
