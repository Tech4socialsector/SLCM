# Copyright (c) 2026, Tech4socialsector and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, format_date


def execute(filters: dict | None = None):
	"""Return columns, data, message, chart, and report summary."""
	filters = dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data, filters)
	report_summary = get_report_summary(data, filters)

	return columns, data, None, chart, report_summary


def get_columns() -> list[dict]:
	"""Return columns for the report."""
	return [
		{
			"label": _("Application ID"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "PACE Application",
			"width": 150
		},
		{
			"label": _("Applicant Name"),
			"fieldname": "applicant_name",
			"fieldtype": "Data",
			"width": 170
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
			"fieldname": "programme",
			"fieldtype": "Link",
			"options": "PACE Programme",
			"width": 180
		},
		{
			"label": _("Academic Year"),
			"fieldname": "academic_year",
			"fieldtype": "Link",
			"options": "Academic Year",
			"width": 130
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 150
		},
		# Date columns hidden as requested:
		# {
		# 	"label": _("Submission Date"),
		# 	"fieldname": "submission_date",
		# 	"fieldtype": "Date",
		# 	"width": 130
		# },
		# {
		# 	"label": _("Completed Date"),
		# 	"fieldname": "completed_date",
		# 	"fieldtype": "Date",
		# 	"width": 130
		# },
		# {
		# 	"label": _("Verified Date"),
		# 	"fieldname": "verified_date",
		# 	"fieldtype": "Date",
		# 	"width": 130
		# },
		# {
		# 	"label": _("Course Fee Paid Date"),
		# 	"fieldname": "fee_paid_date",
		# 	"fieldtype": "Date",
		# 	"width": 140
		# },
		# {
		# 	"label": _("Enrolled Date"),
		# 	"fieldname": "enrolled_date",
		# 	"fieldtype": "Date",
		# 	"width": 130
		# },
		{
			"label": _("Fee Status"),
			"fieldname": "fee_status",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Amount Paid"),
			"fieldname": "paid_amount",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("Assigned Verifier"),
			"fieldname": "assigned_verifier",
			"fieldtype": "Link",
			"options": "User",
			"width": 150
		},
		# {
		# 	"label": _("Created On"),
		# 	"fieldname": "creation_date",
		# 	"fieldtype": "Date",
		# 	"width": 120
		# }
	]


def get_data(filters: dict) -> list[dict]:
	"""Return filtered applications data with payment, verification, and enrollment details."""
	query_filters = {}

	if filters.get("programme"):
		query_filters["programme"] = filters.get("programme")
	if filters.get("academic_year"):
		query_filters["academic_year"] = filters.get("academic_year")

	target_date = filters.get("date")
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")

	# If single date is specified, default date window to target_date
	if target_date:
		from_date = target_date
		to_date = target_date

	applications = frappe.get_all(
		"PACE Application",
		filters=query_filters,
		fields=[
			"name",
			"applicant_name",
			"email_address",
			"mobile_number",
			"programme",
			"academic_year",
			"status",
			"submission_date",
			"assigned_verifier",
			"creation",
			"modified"
		],
		order_by="creation desc"
	)

	if not applications:
		return []

	app_names = [a.name for a in applications]

	# 1. Fetch Receipts split by Fee Type (Application Fee vs Course Fee)
	receipts = frappe.get_all(
		"PACE Receipt",
		filters={"pace_application": ["in", app_names], "docstatus": ["!=", 2]},
		fields=["pace_application", "amount", "fee_type", "payment_date", "creation"]
	)

	app_fee_receipt_map = {}
	course_fee_receipt_map = {}
	total_paid_map = {}

	for r in receipts:
		app_id = r.pace_application
		p_date = getdate(r.payment_date or r.creation)
		amt = flt(r.amount)

		total_paid_map[app_id] = total_paid_map.get(app_id, 0.0) + amt

		fee_type = r.fee_type or ""
		if fee_type == "Application Fee":
			if app_id not in app_fee_receipt_map or p_date < app_fee_receipt_map[app_id]:
				app_fee_receipt_map[app_id] = p_date
		elif fee_type == "Course Fee":
			if app_id not in course_fee_receipt_map or p_date < course_fee_receipt_map[app_id]:
				course_fee_receipt_map[app_id] = p_date
		else:
			# Fallback if fee_type is unspecified
			if app_id not in course_fee_receipt_map or p_date < course_fee_receipt_map[app_id]:
				course_fee_receipt_map[app_id] = p_date

	# 2. Fetch Document Verifications for Verified Date
	doc_verifications = frappe.get_all(
		"PACE Document Verification",
		filters={"application": ["in", app_names]},
		fields=["application", "status", "verified_on", "modified"]
	)
	verified_date_map = {}
	for dv in doc_verifications:
		if dv.status == "Verified" or dv.verified_on:
			v_dt = getdate(dv.verified_on or dv.modified)
			verified_date_map[dv.application] = v_dt

	# 3. Fetch Student Master records for Enrolled Date
	student_records = frappe.get_all(
		"Student Master",
		filters={"application_number": ["in", app_names]},
		fields=["application_number", "date_of_registration", "creation"]
	)
	enrolled_date_map = {}
	for st in student_records:
		enr_dt = getdate(st.date_of_registration or st.creation)
		enrolled_date_map[st.application_number] = enr_dt

	# 4. Fetch Fee Assignments to check total payable
	fee_assignments = frappe.get_all(
		"PACE Applicant Fee Assignment",
		filters={"applicant": ["in", app_names], "docstatus": ["!=", 2]},
		fields=["applicant", "final_payable_amount", "status", "fee_type"]
	)
	payable_map = {}
	for fa in fee_assignments:
		app_id = fa.applicant
		payable_map[app_id] = payable_map.get(app_id, 0.0) + flt(fa.final_payable_amount)

	f_from = getdate(from_date) if from_date else None
	f_to = getdate(to_date) if to_date else None

	data = []
	for row in applications:
		app_id = row.name
		paid_amt = flt(total_paid_map.get(app_id, 0))
		payable_amt = flt(payable_map.get(app_id, 0))

		creation_date = getdate(row.creation)
		sub_date = getdate(row.submission_date) if row.submission_date else None

		# Application Fee paid date -> Completed Date
		completed_date = app_fee_receipt_map.get(app_id)
		if not completed_date and row.status in ["Completed", "Under Verification", "Verified", "Fee Paid", "Enrolled", "Admitted"]:
			completed_date = sub_date or creation_date

		# Verified Date from PACE Document Verification
		verified_date = verified_date_map.get(app_id)
		if not verified_date and row.status in ["Verified", "Fee Paid", "Enrolled", "Admitted"]:
			verified_date = getdate(row.modified)

		# Course Fee paid date -> Fee Paid Date
		course_fee_paid_date = course_fee_receipt_map.get(app_id)
		if not course_fee_paid_date and row.status in ["Fee Paid", "Enrolled", "Admitted"]:
			course_fee_paid_date = getdate(row.modified)

		# Enrolled Date from Student Master or PACE Application status transition
		enrolled_date = enrolled_date_map.get(app_id)
		if not enrolled_date and row.status in ["Enrolled", "Admitted"]:
			enrolled_date = getdate(row.modified)

		# Determine Fee Status
		if paid_amt > 0 and payable_amt > 0 and paid_amt >= payable_amt:
			fee_status = _("Paid")
		elif paid_amt > 0:
			fee_status = _("Partially Paid")
		elif row.status in ["Fee Paid", "Enrolled", "Admitted"]:
			fee_status = _("Paid")
		else:
			fee_status = _("Pending")

		# Date filter matching check for row inclusion
		if f_from and f_to:
			c_match = creation_date and (f_from <= creation_date <= f_to)
			s_match = sub_date and (f_from <= sub_date <= f_to)
			comp_match = completed_date and (f_from <= completed_date <= f_to)
			v_match = verified_date and (f_from <= verified_date <= f_to)
			fee_match = course_fee_paid_date and (f_from <= course_fee_paid_date <= f_to)
			enr_match = enrolled_date and (f_from <= enrolled_date <= f_to)

			if not (c_match or s_match or comp_match or v_match or fee_match or enr_match):
				continue

		rec = {
			"name": row.name,
			"applicant_name": row.applicant_name,
			"email_address": row.email_address,
			"mobile_number": row.mobile_number,
			"programme": row.programme,
			"academic_year": row.academic_year,
			"status": row.status,
			"submission_date": sub_date,
			"completed_date": completed_date,
			"verified_date": verified_date,
			"fee_paid_date": course_fee_paid_date,
			"enrolled_date": enrolled_date,
			"fee_status": fee_status,
			"paid_amount": paid_amt,
			"assigned_verifier": row.assigned_verifier,
			"creation_date": creation_date
		}
		data.append(rec)

	return data


def get_report_summary(data: list[dict], filters: dict) -> list[dict]:
	"""Return summary cards for top of report in requested pipeline order."""
	if not data:
		return []

	target_date = getdate(filters.get("date")) if filters.get("date") else None
	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else target_date
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else target_date

	f_from = getdate(from_date) if from_date else None
	f_to = getdate(to_date) if to_date else None

	total_count = 0
	submitted_count = 0
	completed_count = 0
	verified_count = 0
	fee_paid_count = 0
	enrolled_count = 0

	for row in data:
		status = row.get("status")
		create_dt = row.get("creation_date")
		sub_dt = row.get("submission_date")
		comp_dt = row.get("completed_date")
		ver_dt = row.get("verified_date")
		fee_dt = row.get("fee_paid_date")
		enr_dt = row.get("enrolled_date")

		if f_from and f_to:
			if create_dt and (f_from <= create_dt <= f_to):
				total_count += 1
			if sub_dt and (f_from <= sub_dt <= f_to):
				submitted_count += 1
			if comp_dt and (f_from <= comp_dt <= f_to):
				completed_count += 1
			if ver_dt and (f_from <= ver_dt <= f_to):
				verified_count += 1
			if fee_dt and (f_from <= fee_dt <= f_to):
				fee_paid_count += 1
			if enr_dt and (f_from <= enr_dt <= f_to):
				enrolled_count += 1
		else:
			total_count += 1
			if status in ["Submitted", "Completed", "Under Verification", "Verified", "Fee Paid", "Admitted", "Enrolled"] or sub_dt:
				submitted_count += 1
			if comp_dt or status in ["Completed", "Under Verification", "Verified", "Fee Paid", "Admitted", "Enrolled"]:
				completed_count += 1
			if ver_dt or status in ["Verified", "Fee Paid", "Admitted", "Enrolled"]:
				verified_count += 1
			if fee_dt or row.get("fee_status") == _("Paid") or status in ["Fee Paid", "Admitted", "Enrolled"]:
				fee_paid_count += 1
			if enr_dt or status in ["Enrolled", "Admitted"]:
				enrolled_count += 1

	date_suffix = ""
	if target_date:
		date_suffix = f" ({format_date(target_date, 'dd MMM YYYY')})"

	return [
		{
			"value": total_count,
			"indicator": "Blue",
			"label": _("Total Applicants") + date_suffix,
			"datatype": "Int",
		},
		{
			"value": submitted_count,
			"indicator": "Orange",
			"label": _("Submitted") + date_suffix,
			"datatype": "Int",
		},
		# {
		# 	"value": completed_count,
		# 	"indicator": "Cyan",
		# 	"label": _("Completed") + date_suffix,
		# 	"datatype": "Int",
		# },
		{
			"value": verified_count,
			"indicator": "Light Blue",
			"label": _("Verified") + date_suffix,
			"datatype": "Int",
		},
		{
			"value": fee_paid_count,
			"indicator": "Purple",
			"label": _("Fee Paid") + date_suffix,
			"datatype": "Int",
		},
		{
			"value": enrolled_count,
			"indicator": "Green",
			"label": _("Enrolled") + date_suffix,
			"datatype": "Int",
		}
	]


def get_chart(data: list[dict], filters: dict) -> dict:
	"""Return bar chart breakdown for pipeline stages with distinct colors and full-width bars."""
	if not data:
		return {}

	target_date = getdate(filters.get("date")) if filters.get("date") else None
	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else target_date
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else target_date

	f_from = getdate(from_date) if from_date else None
	f_to = getdate(to_date) if to_date else None

	total_count = 0
	submitted_count = 0
	completed_count = 0
	verified_count = 0
	fee_paid_count = 0
	enrolled_count = 0

	for row in data:
		status = row.get("status")
		create_dt = row.get("creation_date")
		sub_dt = row.get("submission_date")
		comp_dt = row.get("completed_date")
		ver_dt = row.get("verified_date")
		fee_dt = row.get("fee_paid_date")
		enr_dt = row.get("enrolled_date")

		if f_from and f_to:
			if create_dt and (f_from <= create_dt <= f_to):
				total_count += 1
			if sub_dt and (f_from <= sub_dt <= f_to):
				submitted_count += 1
			if comp_dt and (f_from <= comp_dt <= f_to):
				completed_count += 1
			if ver_dt and (f_from <= ver_dt <= f_to):
				verified_count += 1
			if fee_dt and (f_from <= fee_dt <= f_to):
				fee_paid_count += 1
			if enr_dt and (f_from <= enr_dt <= f_to):
				enrolled_count += 1
		else:
			total_count += 1
			if status in ["Submitted", "Completed", "Under Verification", "Verified", "Fee Paid", "Admitted", "Enrolled"] or sub_dt:
				submitted_count += 1
			if comp_dt or status in ["Completed", "Under Verification", "Verified", "Fee Paid", "Admitted", "Enrolled"]:
				completed_count += 1
			if ver_dt or status in ["Verified", "Fee Paid", "Admitted", "Enrolled"]:
				verified_count += 1
			if fee_dt or row.get("fee_status") == _("Paid") or status in ["Fee Paid", "Admitted", "Enrolled"]:
				fee_paid_count += 1
			if enr_dt or status in ["Enrolled", "Admitted"]:
				enrolled_count += 1

	labels = [
		_("Total Applicants"),
		_("Submitted"),
		# _("Completed"),
		_("Verified"),
		_("Fee Paid"),
		_("Enrolled")
	]

	stage_counts = [
		total_count,
		submitted_count,
		# completed_count,
		verified_count,
		fee_paid_count,
		enrolled_count
	]

	colors = ["#1a73e8", "#f39c12", "#17a2b8", "#3498db", "#9b59b6", "#27ae60"]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": _("Count"),
					"values": stage_counts
				}
			]
		},
		"type": "bar",
		"height": 260,
		"colors": ["#1a73e8"]
	}
