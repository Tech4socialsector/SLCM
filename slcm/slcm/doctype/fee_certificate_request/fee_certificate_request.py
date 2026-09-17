# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, fmt_money, formatdate, today

ORDINALS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
ORDINAL_SUFFIXES = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]


def _amt(amount):
	"""Format like the source templates: '1,02,040/-' (no currency symbol)."""
	formatted = fmt_money(flt(amount), precision=0, currency="INR")
	formatted = formatted.replace("₹", "").strip()
	return f"{formatted}/-"

# Fee Component.component_type -> row label used on the certificate, and the
# order those rows appear in. Anything not listed here falls back to its own
# component_type text and is appended after these standard rows.
ROW_DEFS = [
	("Admission Fee", "Admission Fee- one time"),
	("Re-admission Fee", "Re-admission Fee - one time"),
	("Tuition and Facilities Fee", "Tuition and Facilities Fee - Per annum"),
	("Hostel Fee", "Hostel Residential Charges - Per annum"),
	("Housing and Mess Fee", "Hostel Residential and Mess Charges - Per annum"),
	("Mess Charges", "Mess Charges - Per annum"),
	("Student Refundable Deposit", "Refundable Deposits - one time"),
]
ROW_LABELS = dict(ROW_DEFS)
ROW_ORDER = [key for key, _label in ROW_DEFS]


class FeeCertificateRequest(Document):
	def validate(self):
		if self.certificate_mode == "Single Year":
			self.to_academic_year = None
		elif not self.to_academic_year:
			frappe.throw(_("To Academic Year is required for a Multi Year certificate"))

		if not self.years:
			self._populate_years()

	def _populate_years(self):
		if not self.from_academic_year:
			return
		student = frappe.get_doc("Student Master", self.student) if self.student else None
		for ay in _academic_years_between(self.from_academic_year, self.to_academic_year):
			suffix = _ordinal_suffix_for(student, ay) if student else None
			self.append(
				"years",
				{
					"academic_year": ay.name,
					"year_label": f"{suffix} Year" if suffix else "",
				},
			)


@frappe.whitelist()
def preview_academic_years(student, from_academic_year, to_academic_year=None):
	"""Pure computation for the client to populate the (possibly unsaved) Year-wise
	Breakdown table with — never touches the database doc, so it can't clobber
	unsaved edits on the form."""
	if not student or not from_academic_year:
		return []

	frappe.has_permission("Fee Certificate Request", ptype="read", throw=True)

	student_doc = frappe.get_doc("Student Master", student)
	rows = []
	for ay in _academic_years_between(from_academic_year, to_academic_year):
		suffix = _ordinal_suffix_for(student_doc, ay)
		rows.append({"academic_year": ay.name, "year_label": f"{suffix} Year" if suffix else ""})
	return rows


@frappe.whitelist()
def mark_generated(name):
	doc = frappe.get_doc("Fee Certificate Request", name)
	doc.check_permission("write")
	doc.db_set("status", "Generated")
	doc.db_set("generated_on", frappe.utils.now_datetime())


def _academic_years_between(from_ay, to_ay):
	from_year = frappe.get_doc("Academic Year", from_ay)
	if not to_ay or to_ay == from_ay:
		return [from_year]

	to_year = frappe.get_doc("Academic Year", to_ay)
	years = frappe.get_all(
		"Academic Year",
		filters={
			"year_start_date": ["between", [from_year.year_start_date, to_year.year_start_date]],
		},
		fields=["name", "academic_year_name", "year_start_date", "year_end_date"],
		order_by="year_start_date asc",
	)
	return [frappe.get_doc("Academic Year", y.name) for y in years] or [from_year, to_year]


def _year_offset(student, academic_year_doc):
	if not student or not student.academic_year:
		return None
	try:
		batch_start = frappe.get_doc("Academic Year", student.academic_year)
	except frappe.DoesNotExistError:
		return None
	return academic_year_doc.year_start_date.year - batch_start.year_start_date.year


def _ordinal_year_for(student, academic_year_doc):
	"""Roman-numeral ordinal (I/II/III...) used in the narrative sentence."""
	diff = _year_offset(student, academic_year_doc)
	if diff is None:
		return None
	if 0 <= diff < len(ORDINALS):
		return ORDINALS[diff]
	return str(diff + 1)


def _ordinal_suffix_for(student, academic_year_doc):
	"""'1st'/'2nd'/... suffix used as the default Year Label on each row."""
	diff = _year_offset(student, academic_year_doc)
	if diff is None:
		return None
	if 0 <= diff < len(ORDINAL_SUFFIXES):
		return ORDINAL_SUFFIXES[diff]
	return f"{diff + 1}th"


def _year_breakdown(student_name, academic_year, has_scholarship):
	demands = frappe.get_all(
		"Fee Demand",
		filters={"student": student_name, "academic_year": academic_year, "status": ["!=", "Cancelled"]},
		fields=["fee_component", "original_amount", "waiver_amount", "net_payable", "paid_amount", "outstanding_amount"],
	)

	component_types = {}
	if demands:
		fee_components = list({d.fee_component for d in demands})
		component_types = frappe._dict(
			frappe.get_all(
				"Fee Component",
				filters={"name": ["in", fee_components]},
				fields=["name", "component_type"],
				as_list=1,
			)
		)

	totals_by_type = {}
	for d in demands:
		ctype = component_types.get(d.fee_component) or d.fee_component
		row = totals_by_type.setdefault(ctype, {"original": 0, "waiver": 0, "net": 0, "paid": 0, "outstanding": 0})
		row["original"] += d.original_amount or 0
		row["waiver"] += d.waiver_amount or 0
		row["net"] += d.net_payable or 0
		row["paid"] += d.paid_amount or 0
		row["outstanding"] += d.outstanding_amount or 0

	rows = []
	seen = set()
	for ctype in ROW_ORDER:
		if ctype in totals_by_type:
			rows.append({"particulars": ROW_LABELS[ctype], "amount": totals_by_type[ctype]["original"]})
			seen.add(ctype)
	for ctype, amounts in totals_by_type.items():
		if ctype not in seen:
			rows.append({"particulars": ctype, "amount": amounts["original"]})

	total_payable = sum(r["original"] for r in totals_by_type.values())
	total_waiver = sum(r["waiver"] for r in totals_by_type.values()) if has_scholarship else 0
	net_payable = total_payable - total_waiver
	outstanding = sum(r["outstanding"] for r in totals_by_type.values())

	return {
		"rows": rows,
		"total_payable": total_payable,
		"scholarship_amount": total_waiver,
		"net_payable": net_payable,
		"is_fully_paid": outstanding <= 0 and total_payable > 0,
	}


@frappe.whitelist()
def get_fee_certificate_context(request_name):
	request = frappe.get_doc("Fee Certificate Request", request_name)
	request.check_permission("read")

	student = frappe.get_doc("Student Master", request.student)
	settings = frappe.get_single("Fee Certificate Settings")

	year_rows = request.years or []
	if not year_rows:
		# Fallback for requests saved before the Year-wise Breakdown table existed.
		year_rows = [
			frappe._dict({"academic_year": ay.name, "year_label": "", "status_override": ""})
			for ay in _academic_years_between(request.from_academic_year, request.to_academic_year)
		]

	years = []
	for row in year_rows:
		ay = frappe.get_doc("Academic Year", row.academic_year)
		breakdown = _year_breakdown(student.name, ay.name, request.has_scholarship)

		if row.status_override == "Paid":
			breakdown["is_fully_paid"] = True
		elif row.status_override == "Payable":
			breakdown["is_fully_paid"] = False

		year_label = row.year_label or f"{_ordinal_suffix_for(student, ay) or ''} Year".strip()
		ay_label = ay.academic_year_name or ay.name
		show_label_in_column = request.certificate_mode == "Multi Year" and year_label

		years.append(
			{
				"academic_year": ay_label,
				"ordinal_year": _ordinal_year_for(student, ay),
				"year_label": year_label,
				"column_label": f"{ay_label} ({year_label})" if show_label_in_column else ay_label,
				**breakdown,
				"total_payable_fmt": _amt(breakdown["total_payable"]),
				"scholarship_amount_fmt": _amt(breakdown["scholarship_amount"]),
				"net_payable_fmt": _amt(breakdown["net_payable"]),
			}
		)

	current_year_entry = years[-1] if years else None

	summary_parts = []
	for y in years:
		verb = "has paid" if y["is_fully_paid"] else "is required to pay"
		summary_parts.append(f"{verb} Rs.{y['net_payable_fmt']} towards fee for AY {y['academic_year']}")
	summary_sentence = " and ".join(summary_parts)

	table = _build_table(years, request.has_scholarship)

	return {
		"request": request.as_dict(),
		"student": {
			"full_name": student.first_name,
			"registration_id": student.registration_id or student.name,
			"programme": frappe.db.get_value("Programme", student.programme_of_study, "program_name")
			or student.programme_of_study,
		},
		"settings": settings.as_dict(),
		"years": years,
		"current_year": current_year_entry,
		"summary_sentence": summary_sentence,
		"generation_date": formatdate(today(), "dd.mm.yyyy"),
		"table": table,
	}


def _build_table(years, has_scholarship):
	particulars_seen = []
	for y in years:
		for row in y["rows"]:
			if row["particulars"] not in particulars_seen:
				particulars_seen.append(row["particulars"])

	table_rows = []
	for particulars in particulars_seen:
		amounts = []
		for y in years:
			match = next((r for r in y["rows"] if r["particulars"] == particulars), None)
			amounts.append(_amt(match["amount"]) if match else "-")
		table_rows.append({"particulars": particulars, "amounts": amounts})

	any_scholarship = has_scholarship and any(y["scholarship_amount"] for y in years)

	return {
		"year_labels": [y["column_label"] for y in years],
		"rows": table_rows,
		"total_row": [y["total_payable_fmt"] for y in years],
		"show_scholarship_row": any_scholarship,
		"scholarship_row": [y["scholarship_amount_fmt"] for y in years] if any_scholarship else [],
		"net_row": [y["net_payable_fmt"] for y in years] if any_scholarship else [],
	}
