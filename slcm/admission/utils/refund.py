import frappe
from frappe.utils import flt, date_diff, nowdate


def get_applicant_refund_policies(applicant):
	"""
	Fetches refund policies mapped to the applicant's Fee Structure.
	Returns a dict with:
	  - policies: list of active policy dicts sorted by days_from_payment asc
	  - days_since_payment: int
	  - fee_structure: str (name of the matched Fee Structure)
	"""
	# 1. Resolve basic details
	details = frappe.db.get_value(
		"Applicant", applicant,
		["program", "campus", "admission_cycle"],
		as_dict=1
	)
	if not details:
		return {"policies": [], "days_since_payment": 0, "fee_structure": None}

	program = details.program
	campus = details.campus
	cycle = details.admission_cycle

	# 2. Find Fee Structure via Offer Configuration
	fee_structure = None
	config_names = frappe.get_all(
		"Offer Configuration",
		filters={"admission_cycle": cycle, "campus": campus, "is_active": 1},
		pluck="name"
	)

	for cn in config_names:
		config_doc = frappe.get_doc("Offer Configuration", cn)
		for row in config_doc.fee_structure:
			fs_program = frappe.db.get_value("Fee Structure", row.fee_structure, "program")
			if fs_program == program:
				fee_structure = row.fee_structure
				break
		if fee_structure:
			break

	if not fee_structure:
		return {"policies": [], "days_since_payment": 0, "fee_structure": None}

	# 3. Get policies from Fee Structure
	fs_doc = frappe.get_doc("Fee Structure", fee_structure)

	if not fs_doc.is_refund_available:
		return {"policies": [], "days_since_payment": 0, "fee_structure": fee_structure}

	# Collect and sort policies by days_from_payment ascending
	policies = []
	for row in fs_doc.get("refund_policies", []):
		if row.is_active:
			policies.append({
				"policy_name": row.refund_policy,
				"days_from_payment": row.days_from_payment,
				"refund_percentage": row.refund_percentage
			})

	policies = sorted(policies, key=lambda p: p.get("days_from_payment", 0))

	# 4. Calculate days since last payment
	days_since_payment = 0
	last_payment_date = get_last_payment_date(applicant)
	if last_payment_date:
		days_since_payment = date_diff(nowdate(), last_payment_date)

	return {
		"policies": policies,
		"days_since_payment": days_since_payment,
		"fee_structure": fee_structure
	}


def get_last_payment_date(applicant):
	"""
	Returns the date of the most recent submitted payment for the applicant.
	Checks Fee Payment first, then falls back to Applicant Payment Receipt.
	"""
	last_fee_payment = frappe.db.get_value(
		"Fee Payment",
		{"applicant": applicant, "status": "Submitted"},
		"payment_date",
		order_by="payment_date desc"
	)

	last_receipt = frappe.db.get_value(
		"Applicant Payment Receipt",
		{"applicant": applicant, "docstatus": 1},
		"payment_date",
		order_by="payment_date desc"
	)

	return last_fee_payment or last_receipt
