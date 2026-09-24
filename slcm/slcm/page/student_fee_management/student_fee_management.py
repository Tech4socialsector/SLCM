import frappe
from frappe import _
from frappe.utils import cint, flt, today

ALLOWED_ROLES = ("System Manager", "Campus Admin", "Accounts Manager", "Accounts User")

# Demand-level aggregate per student. Cancelled demands never count toward dues.
_DEMAND_AGG = """
	SELECT
		student,
		COUNT(*)                                                         AS demand_count,
		SUM(net_payable)                                                 AS total_payable,
		SUM(paid_amount)                                                 AS paid_amount,
		SUM(waiver_amount)                                               AS waiver_amount,
		SUM(outstanding_amount)                                          AS outstanding_amount,
		SUM(CASE WHEN status = 'Overdue' THEN outstanding_amount ELSE 0 END) AS overdue_amount
	FROM `tabFee Demand`
	WHERE status != 'Cancelled'
	GROUP BY student
"""

# Excess = unused balance on active (submitted) credit notes.
_CREDIT_AGG = """
	SELECT student, SUM(available_credit) AS excess_amount
	FROM `tabStudent Credit Note`
	WHERE docstatus = 1 AND status = 'Active'
	GROUP BY student
"""


def _check_access():
	frappe.only_for(ALLOWED_ROLES)


@frappe.whitelist()
def get_filter_options():
	"""Academic years, terms (with their year, for dependent filtering) and programmes present on students."""
	_check_access()

	years = frappe.db.sql_list(
		"""SELECT DISTINCT academic_year FROM `tabStudent Master`
		WHERE IFNULL(academic_year, '') != '' ORDER BY academic_year DESC"""
	)
	terms = frappe.db.sql(
		"""SELECT DISTINCT academic_year, academic_term FROM `tabStudent Master`
		WHERE IFNULL(academic_term, '') != '' ORDER BY academic_term""",
		as_dict=True,
	)
	programmes = frappe.db.sql(
		"""SELECT DISTINCT sm.programme_of_study AS name, p.program_name
		FROM `tabStudent Master` sm
		LEFT JOIN `tabProgramme` p ON p.name = sm.programme_of_study
		WHERE IFNULL(sm.programme_of_study, '') != ''
		ORDER BY sm.programme_of_study""",
		as_dict=True,
	)
	return {"academic_years": years, "terms": terms, "programmes": programmes}


@frappe.whitelist()
def get_students(
	academic_year=None,
	academic_term=None,
	programme=None,
	dues_status=None,
	search=None,
	start=0,
	page_length=50,
	sort_by=None,
	sort_order=None,
):
	"""Paginated student list with per-student fee totals, plus totals across the whole filtered set."""
	_check_access()

	conditions = ["1=1"]
	values = {}
	if academic_year:
		conditions.append("sm.academic_year = %(academic_year)s")
		values["academic_year"] = academic_year
	if academic_term:
		conditions.append("sm.academic_term = %(academic_term)s")
		values["academic_term"] = academic_term
	if programme:
		conditions.append("sm.programme_of_study = %(programme)s")
		values["programme"] = programme
	if search:
		conditions.append(
			"(sm.name LIKE %(search)s OR sm.first_name LIKE %(search)s "
			"OR sm.registration_id LIKE %(search)s OR sm.official_email_id LIKE %(search)s)"
		)
		values["search"] = f"%{search.strip()}%"

	status_conditions = {
		"pending": "IFNULL(fd.outstanding_amount, 0) > 0",
		"overdue": "IFNULL(fd.overdue_amount, 0) > 0",
		"cleared": "IFNULL(fd.demand_count, 0) > 0 AND IFNULL(fd.outstanding_amount, 0) = 0",
		"excess": "IFNULL(cn.excess_amount, 0) > 0",
		"no_demands": "IFNULL(fd.demand_count, 0) = 0",
	}
	if dues_status in status_conditions:
		conditions.append(status_conditions[dues_status])

	base = f"""
		FROM `tabStudent Master` sm
		LEFT JOIN ({_DEMAND_AGG}) fd ON fd.student = sm.name
		LEFT JOIN ({_CREDIT_AGG}) cn ON cn.student = sm.name
		WHERE {" AND ".join(conditions)}
	"""

	totals = frappe.db.sql(
		f"""SELECT
			COUNT(*)                              AS student_count,
			SUM(IFNULL(fd.total_payable, 0))      AS total_payable,
			SUM(IFNULL(fd.paid_amount, 0))        AS paid_amount,
			SUM(IFNULL(fd.outstanding_amount, 0)) AS outstanding_amount,
			SUM(IFNULL(fd.overdue_amount, 0))     AS overdue_amount,
			SUM(IFNULL(cn.excess_amount, 0))      AS excess_amount
		{base}""",
		values,
		as_dict=True,
	)[0]

	values.update(start=cint(start), page_length=min(cint(page_length) or 50, 500))
	rows = frappe.db.sql(
		f"""SELECT
			sm.name AS student, sm.first_name AS student_name, sm.registration_id,
			sm.official_email_id, sm.email, sm.programme_of_study, sm.batch,
			sm.academic_year, sm.academic_term, sm.section, sm.student_status,
			IFNULL(fd.demand_count, 0)       AS demand_count,
			IFNULL(fd.total_payable, 0)      AS total_payable,
			IFNULL(fd.paid_amount, 0)        AS paid_amount,
			IFNULL(fd.waiver_amount, 0)      AS waiver_amount,
			IFNULL(fd.outstanding_amount, 0) AS outstanding_amount,
			IFNULL(fd.overdue_amount, 0)     AS overdue_amount,
			IFNULL(cn.excess_amount, 0)      AS excess_amount
		{base}
		ORDER BY {_order_by(sort_by, sort_order)}
		LIMIT %(start)s, %(page_length)s""",
		values,
		as_dict=True,
	)
	_attach_receipt_info(rows)

	return {"rows": rows, "totals": totals}


# Sortable columns → SQL expressions. Only these keys are accepted, so sort input never reaches SQL raw.
_SORT_COLUMNS = {
	"student": ["sm.first_name"],
	"programme": ["sm.programme_of_study"],
	"year_term": ["sm.academic_year", "sm.academic_term"],
	"batch": ["sm.batch"],
	"demand_count": ["IFNULL(fd.demand_count, 0)"],
	"total_payable": ["IFNULL(fd.total_payable, 0)"],
	"paid_amount": ["IFNULL(fd.paid_amount, 0)"],
	"outstanding_amount": ["IFNULL(fd.outstanding_amount, 0)"],
	"excess_amount": ["IFNULL(cn.excess_amount, 0)"],
	# Same precedence as the list's status badge: Overdue > Pending > Cleared > No Demands
	"status": [
		"""CASE WHEN IFNULL(fd.demand_count, 0) = 0 THEN 0
			WHEN IFNULL(fd.overdue_amount, 0) > 0 THEN 3
			WHEN IFNULL(fd.outstanding_amount, 0) > 0 THEN 2
			ELSE 1 END"""
	],
}


def _order_by(sort_by, sort_order):
	if sort_by not in _SORT_COLUMNS:
		return "IFNULL(fd.outstanding_amount, 0) DESC, sm.first_name ASC, sm.name ASC"
	direction = "ASC" if (sort_order or "").lower() == "asc" else "DESC"
	return ", ".join(f"{col} {direction}" for col in _SORT_COLUMNS[sort_by]) + ", sm.name ASC"


def _attach_receipt_info(rows):
	"""Add receipt_count and latest_receipt (active Fee Receipts) to each student row on the page."""
	if not rows:
		return
	receipts = frappe.get_all(
		"Fee Receipt",
		filters={"student": ["in", [r.student for r in rows]], "status": ["!=", "Cancelled"]},
		fields=["name", "student"],
		order_by="receipt_date desc, creation desc",
	)
	by_student = {}
	for rc in receipts:
		by_student.setdefault(rc.student, []).append(rc.name)
	for r in rows:
		names = by_student.get(r.student, [])
		r["receipt_count"] = len(names)
		r["latest_receipt"] = names[0] if names else None


@frappe.whitelist()
def get_student_receipts(student):
	"""Active Fee Receipts for one student, newest first, with the demands each one settled."""
	_check_access()

	receipts = frappe.get_all(
		"Fee Receipt",
		filters={"student": student, "status": ["!=", "Cancelled"]},
		fields=["name", "receipt_date", "amount", "payment_mode", "reference_number", "fee_payment"],
		order_by="receipt_date desc, creation desc",
	)
	if receipts:
		paid = frappe.get_all(
			"Fee Receipt Demands Paid",
			filters={"parent": ["in", [r.name for r in receipts]], "parenttype": "Fee Receipt"},
			fields=["parent", "fee_demand", "description"],
			order_by="idx asc",
		)
		by_parent = {}
		for row in paid:
			by_parent.setdefault(row.parent, []).append(row.description or row.fee_demand)
		for r in receipts:
			r["demands"] = by_parent.get(r.name, [])
	return receipts


@frappe.whitelist()
def download_receipt(receipt):
	"""
	PDF of an existing Fee Receipt using its standard "Fee Receipt" print format.
	Access is gated by this page's roles (Accounts roles don't have read on Fee Receipt itself).
	"""
	_check_access()

	doc = frappe.get_doc("Fee Receipt", receipt)
	if doc.status == "Cancelled":
		frappe.throw(_("Receipt {0} has been cancelled.").format(receipt))

	frappe.flags.ignore_print_permissions = True
	try:
		pdf = frappe.get_print("Fee Receipt", doc.name, "Fee Receipt", doc=doc, as_pdf=True)
	finally:
		frappe.flags.ignore_print_permissions = False

	frappe.local.response.filename = "{0}.pdf".format(doc.name.replace(" ", "-").replace("/", "-"))
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "pdf"


@frappe.whitelist()
def get_student_dues(student):
	"""Everything the student detail view needs: profile, summary, demands, payments, credits, refunds."""
	_check_access()

	if not frappe.db.exists("Student Master", student):
		frappe.throw(_("Student {0} not found.").format(student))

	profile = frappe.db.get_value(
		"Student Master",
		student,
		[
			"name", "first_name", "registration_id", "official_email_id", "email", "phone",
			"programme_of_study", "batch", "academic_year", "academic_term", "section",
			"student_status", "passport_size_photo",
		],
		as_dict=True,
	)
	if profile.programme_of_study:
		profile.update(
			frappe.db.get_value(
				"Programme", profile.programme_of_study, ["program_name", "department"], as_dict=True
			)
			or {}
		)

	demands = frappe.get_all(
		"Fee Demand",
		filters={"student": student},
		fields=[
			"name", "demand_type", "fee_component", "description", "status",
			"demand_date", "due_date", "creation", "academic_year",
			"original_amount", "penalty_amount", "waiver_amount", "net_payable",
			"paid_amount", "credit_adjusted", "outstanding_amount", "refunded_amount",
			"is_refundable", "last_payment_date", "remarks",
		],
		order_by="demand_date desc, creation desc",
	)

	# Receipts that settled each demand (a receipt can cover several demands, a demand several receipts)
	receipt_rows = frappe.db.sql(
		"""SELECT rdp.fee_demand, fr.name, fr.receipt_date, fr.payment_mode, rdp.amount
		FROM `tabFee Receipt Demands Paid` rdp
		JOIN `tabFee Receipt` fr ON fr.name = rdp.parent AND rdp.parenttype = 'Fee Receipt'
		WHERE fr.student = %s AND IFNULL(fr.status, '') != 'Cancelled'
		ORDER BY fr.receipt_date DESC, fr.creation DESC""",
		student,
		as_dict=True,
	)
	by_demand = {}
	for r in receipt_rows:
		by_demand.setdefault(r.pop("fee_demand"), []).append(r)
	for d in demands:
		d["receipts"] = by_demand.get(d.name, [])

	payments = frappe.get_all(
		"Fee Payment",
		filters={"student": student},
		fields=[
			"name", "payment_date", "payment_mode", "amount", "reference_number",
			"transaction_date", "status", "docstatus", "receipt", "remarks",
		],
		order_by="payment_date desc, creation desc",
	)
	if payments:
		rows = frappe.get_all(
			"Fee Payment Demand Row",
			filters={"parent": ["in", [p.name for p in payments]], "parenttype": "Fee Payment"},
			fields=["parent", "fee_demand", "demand_description", "amount_allocated"],
			order_by="idx asc",
		)
		by_parent = {}
		for r in rows:
			by_parent.setdefault(r.parent, []).append(r)
		for p in payments:
			p["allocations"] = by_parent.get(p.name, [])

	credit_notes = frappe.get_all(
		"Student Credit Note",
		filters={"student": student, "docstatus": 1},
		fields=[
			"name", "credit_type", "academic_year", "credit_amount", "available_credit",
			"used_credit", "status", "source_receipt", "remarks", "creation",
		],
		order_by="creation desc",
	)
	if credit_notes:
		adjustments = frappe.get_all(
			"Credit Adjustment Row",
			filters={"parent": ["in", [c.name for c in credit_notes]], "parenttype": "Student Credit Note"},
			fields=["parent", "fee_demand", "fee_component", "amount_adjusted", "adjusted_on", "adjusted_by"],
			order_by="idx asc",
		)
		by_parent = {}
		for a in adjustments:
			by_parent.setdefault(a.parent, []).append(a)
		for c in credit_notes:
			c["adjustments"] = by_parent.get(c.name, [])

	refunds = frappe.get_all(
		"Fee Refund",
		filters={"student": student},
		fields=[
			"name", "fee_demand", "fee_component", "refund_type", "refund_amount",
			"refund_date", "refund_mode", "utr_number", "status", "docstatus", "reason",
		],
		order_by="refund_date desc, creation desc",
	)

	active = [d for d in demands if d.status != "Cancelled"]
	summary = {
		"total_payable": sum(flt(d.net_payable) for d in active),
		"paid_amount": sum(flt(d.paid_amount) for d in active),
		"waiver_amount": sum(flt(d.waiver_amount) for d in active),
		"penalty_amount": sum(flt(d.penalty_amount) for d in active),
		"pending_amount": sum(flt(d.outstanding_amount) for d in active),
		"overdue_amount": sum(flt(d.outstanding_amount) for d in active if d.status == "Overdue"),
		"excess_amount": sum(
			flt(c.available_credit) for c in credit_notes if c.status == "Active"
		),
		"refunded_amount": sum(flt(r.refund_amount) for r in refunds if r.docstatus == 1),
	}

	return {
		"profile": profile,
		"summary": summary,
		"demands": demands,
		"payments": payments,
		"credit_notes": credit_notes,
		"refunds": refunds,
	}


@frappe.whitelist()
def record_payment(
	student,
	allocations,
	payment_mode,
	payment_date=None,
	reference_number=None,
	transaction_date=None,
	bank_name=None,
	remarks=None,
):
	"""
	Record one Fee Payment against one or more of a student's demands and submit it.
	allocations: JSON list of {"fee_demand": ..., "amount": ...}.
	Submitting runs the existing Fee Payment pipeline (demand status update, receipt, payment log).
	"""
	_check_access()

	allocations = frappe.parse_json(allocations) or []
	allocations = [a for a in allocations if flt(a.get("amount")) > 0]
	if not allocations:
		frappe.throw(_("Enter an amount for at least one demand."))

	demand_names = [a["fee_demand"] for a in allocations]
	demands = {
		d.name: d
		for d in frappe.get_all(
			"Fee Demand",
			filters={"name": ["in", demand_names]},
			fields=["name", "student", "description", "fee_component", "outstanding_amount", "status"],
		)
	}
	for a in allocations:
		d = demands.get(a["fee_demand"])
		if not d or d.student != student:
			frappe.throw(_("Fee Demand {0} does not belong to this student.").format(a["fee_demand"]))
		if d.status in ("Paid", "Cancelled", "Waived"):
			frappe.throw(_("Fee Demand {0} is {1} and cannot take a payment.").format(d.name, d.status))

	payment = frappe.new_doc("Fee Payment")
	payment.student = student
	payment.payment_date = payment_date or today()
	payment.payment_mode = payment_mode
	payment.reference_number = reference_number
	payment.transaction_date = transaction_date
	payment.bank_name = bank_name
	payment.remarks = remarks
	payment.amount = sum(flt(a["amount"]) for a in allocations)
	for a in allocations:
		d = demands[a["fee_demand"]]
		payment.append("payment_demands", {
			"fee_demand": d.name,
			"demand_description": d.description or d.fee_component,
			"outstanding_amount": d.outstanding_amount,
			"amount_allocated": flt(a["amount"]),
		})
	payment.insert()
	payment.submit()

	return {"payment": payment.name, "receipt": payment.receipt}


@frappe.whitelist()
def apply_excess_credit(student, fee_demand, amount):
	"""Adjust a student's excess (active credit notes, oldest first) against one demand."""
	_check_access()

	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Amount must be greater than zero."))

	demand = frappe.db.get_value(
		"Fee Demand", fee_demand, ["student", "outstanding_amount", "status"], as_dict=True
	)
	if not demand or demand.student != student:
		frappe.throw(_("Fee Demand {0} does not belong to this student.").format(fee_demand))
	if demand.status in ("Paid", "Cancelled", "Waived"):
		frappe.throw(_("Fee Demand {0} is {1}.").format(fee_demand, demand.status))
	if amount > flt(demand.outstanding_amount):
		frappe.throw(
			_("Amount ({0}) exceeds the outstanding amount ({1}).").format(
				frappe.utils.fmt_money(amount, currency="INR"),
				frappe.utils.fmt_money(demand.outstanding_amount, currency="INR"),
			)
		)

	notes = frappe.get_all(
		"Student Credit Note",
		filters={"student": student, "docstatus": 1, "status": "Active", "available_credit": [">", 0]},
		fields=["name", "available_credit"],
		order_by="creation asc",
	)
	if amount > sum(flt(n.available_credit) for n in notes):
		frappe.throw(_("Amount exceeds the student's available excess."))

	remaining = amount
	used = []
	for n in notes:
		if remaining <= 0:
			break
		take = min(remaining, flt(n.available_credit))
		frappe.get_doc("Student Credit Note", n.name).apply_credit_to_demand(fee_demand, take)
		used.append(n.name)
		remaining -= take

	return {"credit_notes": used}


@frappe.whitelist()
def cancel_demand(fee_demand):
	_check_access()
	return frappe.get_doc("Fee Demand", fee_demand).cancel_demand()
