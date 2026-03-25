from __future__ import unicode_literals
import frappe
from frappe import _


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		# ── Candidate Details ─────────────────────────────────────────
		{
			"fieldname": "name",
			"label": _("Application No."),
			"fieldtype": "Link",
			"options": "Foundations for a Legal Education",
			"width": 150,
		},
		{
			"fieldname": "timestamp",
			"label": _("Submission Date"),
			"fieldtype": "Datetime",
			"width": 160,
		},
		{
			"fieldname": "candidate_name",
			"label": _("Name on Certificate"),
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"fieldname": "email_address",
			"label": _("Email Address"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "candidate_email_id",
			"label": _("Candidate's Email ID"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "candidate_current_occupation",
			"label": _("Current Occupation"),
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"fieldname": "candidate_gender",
			"label": _("Gender"),
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"fieldname": "candidate_dob",
			"label": _("Date of Birth"),
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"fieldname": "candidate_nationality",
			"label": _("Nationality"),
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "country_of_residence",
			"label": _("Country of Residence"),
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"fieldname": "candidates_state",
			"label": _("State"),
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"fieldname": "city",
			"label": _("City"),
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "address_line_1",
			"label": _("Address Line 1"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "pincode",
			"label": _("Pincode"),
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"fieldname": "candidate_contact_number",
			"label": _("Contact Number"),
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"fieldname": "where_did_you_hear",
			"label": _("Where Did You Hear About FLE?"),
			"fieldtype": "Data",
			"width": 200,
		},
		# ── Educational Background ─────────────────────────────────────
		{
			"fieldname": "last_class_attended",
			"label": _("Last Examination Attended"),
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"fieldname": "latest_board_attended",
			"label": _("Latest Board"),
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"fieldname": "year_of_passing",
			"label": _("Year of Passing"),
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "last_institution_attended",
			"label": _("Last Institution Attended"),
			"fieldtype": "Data",
			"width": 200,
		},
		# ── Parent / Guardian Details ──────────────────────────────────
		{
			"fieldname": "relationship_with_candidate",
			"label": _("Relationship with Candidate"),
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"fieldname": "parent_name",
			"label": _("Parent/Guardian Name"),
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"fieldname": "parent_contact_number",
			"label": _("Parent Contact Number"),
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"fieldname": "parent_email_address",
			"label": _("Parent Email Address"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "parent_occupation",
			"label": _("Parent's Occupation"),
			"fieldtype": "Data",
			"width": 150,
		},
		# ── Payment Details ────────────────────────────────────────────
		{
			"fieldname": "payment_status",
			"label": _("Payment Status"),
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"fieldname": "paid_amount",
			"label": _("Paid Amount"),
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"fieldname": "payment_id",
			"label": _("Payment ID"),
			"fieldtype": "Data",
			"width": 180,
		},
		# ── Application Status ─────────────────────────────────────────
		{
			"fieldname": "enrollment_status",
			"label": _("Enrollment Status"),
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"fieldname": "declaration_consent",
			"label": _("Declaration Consent"),
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"fieldname": "lms_account_created",
			"label": _("LMS Account Created"),
			"fieldtype": "Data",
			"width": 140,
		},
		# ── Attached Files ─────────────────────────────────────────────
		{
			"fieldname": "candidate_photo",
			"label": _("Candidate Photo"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "id_card_scan",
			"label": _("ID Card Scan"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "signature_scan",
			"label": _("Signature Scan"),
			"fieldtype": "Data",
			"width": 200,
		},
	]


def get_data(filters):
	conditions = _build_conditions(filters)

	rows = frappe.db.sql(
		f"""
		SELECT
			name,
			timestamp,
			candidate_name,
			email_address,
			candidate_email_id,
			candidate_current_occupation,
			if_other4,
			candidate_gender,
			candidate_dob,
			candidate_nationality,
			country_of_residence,
			candidates_state,
			if_other3,
			city,
			address_line_1,
			pincode,
			candidate_contact_number,
			where_did_you_hear,
			if_others_mention_here,
			last_class_attended,
			if_others1,
			latest_board_attended,
			if_others2,
			year_of_passing,
			please_specify_the_year_of_passing,
			last_institution_attended,
			relationship_with_candidate,
			parent_name,
			parent_contact_number,
			parent_email_address,
			parent_occupation,
			payment_status,
			paid_amount,
			payment_id,
			enrollment_status,
			declaration_consent,
			lms_account_created,
			candidate_photo,
			id_card_scan,
			signature_scan
		FROM `tabFoundations for a Legal Education`
		{conditions}
		ORDER BY timestamp DESC
		""",
		filters or {},
		as_dict=True,
	)

	base_url = frappe.utils.get_url()
	data = []
	for r in rows:
		# Resolve "Other" values
		occupation = r.candidate_current_occupation or ""
		if occupation == "Other" and r.if_other4:
			occupation = f"Other ({r.if_other4})"

		state = r.candidates_state or ""
		if state == "Other" and r.if_other3:
			state = f"Other ({r.if_other3})"

		where_heard = r.where_did_you_hear or ""
		if where_heard == "Other" and r.if_others_mention_here:
			where_heard = f"Other ({r.if_others_mention_here})"

		exam = r.last_class_attended or ""
		if exam == "Other" and r.if_others1:
			exam = f"Other ({r.if_others1})"

		board = r.latest_board_attended or ""
		if board == "Other" and r.if_others2:
			board = f"Other ({r.if_others2})"

		year = r.year_of_passing or ""
		if year == "Prior to 2016" and r.please_specify_the_year_of_passing:
			year = f"Prior to 2016 ({r.please_specify_the_year_of_passing})"

		def file_link(path):
			if not path:
				return ""
			if path.startswith("http://") or path.startswith("https://"):
				return path
			return base_url + path

		data.append({
			"name": r.name,
			"timestamp": r.timestamp,
			"candidate_name": r.candidate_name,
			"email_address": r.email_address,
			"candidate_email_id": r.candidate_email_id,
			"candidate_current_occupation": occupation,
			"candidate_gender": r.candidate_gender,
			"candidate_dob": r.candidate_dob,
			"candidate_nationality": r.candidate_nationality,
			"country_of_residence": r.country_of_residence,
			"candidates_state": state,
			"city": r.city,
			"address_line_1": r.address_line_1,
			"pincode": r.pincode,
			"candidate_contact_number": r.candidate_contact_number,
			"where_did_you_hear": where_heard,
			"last_class_attended": exam,
			"latest_board_attended": board,
			"year_of_passing": year,
			"last_institution_attended": r.last_institution_attended,
			"relationship_with_candidate": r.relationship_with_candidate,
			"parent_name": r.parent_name,
			"parent_contact_number": r.parent_contact_number,
			"parent_email_address": r.parent_email_address,
			"parent_occupation": r.parent_occupation,
			"payment_status": r.payment_status,
			"paid_amount": r.paid_amount,
			"payment_id": r.payment_id,
			"enrollment_status": r.enrollment_status,
			"declaration_consent": "Yes" if r.declaration_consent else "No",
			"lms_account_created": "Yes" if r.lms_account_created else "No",
			"candidate_photo": file_link(r.candidate_photo),
			"id_card_scan": file_link(r.id_card_scan),
			"signature_scan": file_link(r.signature_scan),
		})

	return data


def _build_conditions(filters):
	if not filters:
		return ""

	clauses = []

	if filters.get("payment_status"):
		clauses.append("payment_status = %(payment_status)s")

	if filters.get("enrollment_status"):
		clauses.append("enrollment_status = %(enrollment_status)s")

	if filters.get("candidate_gender"):
		clauses.append("candidate_gender = %(candidate_gender)s")

	if filters.get("candidate_nationality"):
		clauses.append("candidate_nationality = %(candidate_nationality)s")

	if filters.get("candidates_state"):
		clauses.append("candidates_state = %(candidates_state)s")

	if filters.get("year_of_passing"):
		clauses.append("year_of_passing = %(year_of_passing)s")

	if filters.get("lms_account_created") is not None:
		clauses.append("lms_account_created = %(lms_account_created)s")

	if filters.get("from_date"):
		clauses.append("DATE(timestamp) >= %(from_date)s")

	if filters.get("to_date"):
		clauses.append("DATE(timestamp) <= %(to_date)s")

	return ("WHERE " + " AND ".join(clauses)) if clauses else ""
