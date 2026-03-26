# Copyright (c) 2026, TFSS and contributors
# Application fee payment service - integrates with Payment Request and Applicant Fee Assignment

import frappe
from frappe import _
from frappe.utils import flt


def get_application_fee_for_category(program, admission_cycle, category):
	"""
	Returns the application fee amount from Program Reservation Policy
	based on program, admission_cycle, and category (Admission Category name).

	Look up Program Reservation Policy for the given program+cycle,
	then find the Program Reservation Category row where category_name matches.
	Returns application_fee or 0 if not found.
	"""
	if not program or not admission_cycle:
		return 0

	policy = frappe.db.get_value(
		"Program Reservation Policy",
		{"program": program, "admission_cycle": admission_cycle, "status": "Active"},
		"name"
	)
	if not policy:
		policy = frappe.db.get_value(
			"Program Reservation Policy",
			{"program": program, "admission_cycle": admission_cycle},
			"name"
		)
	if not policy:
		return 0

	rows = frappe.get_all(
		"Program Reservation Category",
		filters={"parent": policy, "parenttype": "Program Reservation Policy"},
		fields=["category_name", "application_fee"]
	)

	category_str = (category or "").strip()
	for row in rows:
		if row.category_name == category_str or (row.category_name and row.category_name.strip() == category_str):
			return flt(row.application_fee, 2)

	for row in rows:
		if (row.category_name or "").lower() in ("general", "gen", "unreserved", ""):
			return flt(row.application_fee, 2)

	return 0


def get_payment_gateway_for_application_fee(program, admission_cycle):
	"""
	Returns the Payment Gateway from Program Reservation Policy for the given program and admission_cycle.
	Uses the same policy lookup as get_application_fee_for_category (Active first, then any).
	"""
	if not program or not admission_cycle:
		return None
	gateway = frappe.db.get_value(
		"Program Reservation Policy",
		{"program": program, "admission_cycle": admission_cycle, "status": "Active"},
		"payment_gateway"
	)
	if not gateway:
		gateway = frappe.db.get_value(
			"Program Reservation Policy",
			{"program": program, "admission_cycle": admission_cycle},
			"payment_gateway"
		)
	return gateway


def get_or_create_application_fee_component():
	"""Ensures 'Application Fee' Fee Component exists for AFA child rows."""
	if frappe.db.exists("Fee Component", "Application Fee"):
		return "Application Fee"
	comp = frappe.new_doc("Fee Component")
	comp.component_name = "Application Fee"
	comp.component_type = "Other"
	comp.amount = 0
	comp.insert(ignore_permissions=True)
	return comp.name


def create_application_fee_assignment(applicant_name):
	"""
	Creates an Applicant Fee Assignment for the given Applicant.
	Uses Program Reservation Policy to get fee amount based on reservation category.
	"""
	applicant = frappe.get_doc("Applicant", applicant_name)

	existing = frappe.db.get_value(
		"Applicant Fee Assignment",
		{"applicant": applicant_name, "fee_type": "Application Fee", "status": ["!=", "Cancelled"]},
		"name"
	)
	if existing:
		return existing

	category = _get_applicant_category(applicant_name)

	fee_amount = get_application_fee_for_category(
		applicant.program, applicant.admission_cycle, category
	)

	if fee_amount > 0:
		frappe.db.set_value("Applicant", applicant_name, "application_fee_amount", fee_amount)
		frappe.db.commit()

	fee_comp = get_or_create_application_fee_component()

	assignment = frappe.new_doc("Applicant Fee Assignment")
	assignment.applicant = applicant_name
	assignment.fee_type = "Application Fee"
	assignment.program = applicant.program
	assignment.admission_cycle = applicant.admission_cycle
	assignment.academic_year = applicant.academic_year
	assignment.assignment_date = frappe.utils.today()
	assignment.scholarship_amount = 0
	assignment.scholarship_applied = 0

	assignment.append("fee_components", {
		"fee_component": fee_comp,
		"component_name": "Application Fee",
		"amount": fee_amount,
		"is_taxable": 0,
		"tax_rate": 0,
		"tax_amount": 0,
		"total_amount": fee_amount
	})

	assignment.insert(ignore_permissions=True)
	assignment.submit()

	return assignment.name


def _get_applicant_category(applicant_name):
	"""
	Get reservation category for fee calculation.

	Order of preference:
	1. Applicant Category child rows – prefer specific reserved categories (SC/ST/OBC-NCL)
	   over generic ones like "General" / "Unreserved".
	2. If child rows are missing or only General, fall back to Applicant.whether_scstobc_ncl
	   when it is set to a reserved value.
	"""
	rows = frappe.get_all(
		"Applicant Category",
		filters={"parent": applicant_name, "parenttype": "Applicant"},
		fields=["category"],
		order_by="idx asc",
	)

	# 1) Prefer explicit categories from child table
	if rows:
		for row in rows:
			name = (row.category or "").strip()
			if name and name.lower() not in ("general", "gen", "unreserved"):
				return name

	# 2) Fallback to Applicant.whether_scstobc_ncl when it's a reserved code
	raw = frappe.db.get_value("Applicant", applicant_name, "whether_scstobc_ncl") or ""
	code = raw.strip()
	if code and code.upper() in {"SC", "ST", "OBC-NCL"}:
		return code

	# 3) Last resort: use first child row (usually General), or None
	if rows:
		return (rows[0].category or "").strip() or None
	return None


@frappe.whitelist()
def get_application_fee_details(applicant_name):
	"""
	Returns application fee amount and status for the given Applicant.
	Used by the portal UI to show fee and enable/disable pay button.
	"""
	applicant = frappe.get_doc("Applicant", applicant_name)
	category = _get_applicant_category(applicant_name)

	fee_amount = get_application_fee_for_category(
		applicant.program, applicant.admission_cycle, category
	)

	if fee_amount != flt(applicant.application_fee_amount):
		frappe.db.set_value("Applicant", applicant_name, "application_fee_amount", fee_amount)
		frappe.db.commit()

	status = applicant.application_fee_status or "Pending"

	payment_gateway = get_payment_gateway_for_application_fee(
		applicant.program, applicant.admission_cycle
	)

	return {
		"applicant_name": applicant_name,
		"fee_amount": fee_amount,
		"application_fee_status": status,
		"reservation_category": category,
		"program": applicant.program,
		"can_submit": status in ("Paid", "Waived"),
		"online_payment_enabled": True,
		"payment_gateway": payment_gateway
	}
