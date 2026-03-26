# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.model.document import Document
from frappe.utils import flt, add_days, nowdate


class ApplicantFeeAssignment(Document):
	def validate(self):
		self.validate_reference()
		self.set_metadata()
		self.set_notification_receiver()
		self.apply_scholarship()
		self.calculate_totals()
		self.validate_status_change()

	def validate_reference(self):
		"""Require either offer_letter (Admission Fee) or applicant for Application Fee."""
		if self.offer_letter:
			self.fee_type = "Admission Fee"
		else:
			self.fee_type = "Application Fee"
			if self.applicant:
				meta = frappe.db.get_value("Applicant", self.applicant,
					["program", "admission_cycle", "academic_year"], as_dict=True)
				if meta:
					self.program = meta.program
					self.admission_cycle = meta.admission_cycle
					if meta.academic_year:
						self.academic_year = meta.academic_year

	def set_metadata(self):
		if self.applicant:
			if not self.admission_cycle or not self.academic_year:
				metadata = frappe.db.get_value("Applicant", self.applicant,
					["admission_cycle", "academic_year"], as_dict=True)
				if metadata:
					if not self.admission_cycle:
						self.admission_cycle = metadata.admission_cycle
					if not self.academic_year:
						self.academic_year = metadata.academic_year

	def set_notification_receiver(self):
		if self.applicant:
			applicant_email = frappe.db.get_value("Applicant", self.applicant, "email")
			if applicant_email:
				user_name = frappe.db.get_value("User", {"email": applicant_email}, "name")
				if user_name:
					self.notification_receiver = user_name

	def apply_scholarship(self):
		"""
		Fetches the total approved scholarship amount for this applicant + cycle
		and stores it directly in the scholarship_amount field.
		No Fee Component link row is added — scholarship is tracked as a separate field.
		Application Fee assignments do not apply scholarship.
		"""
		if self.fee_type == "Application Fee" or not self.applicant or not self.admission_cycle:
			return

		total_benefit = frappe.db.sql("""
			SELECT SUM(calculated_benefit)
			FROM `tabScholarship Application`
			WHERE applicant_id = %s
			AND admission_cycle = %s
			AND status = 'Approved'
		""", (self.applicant, self.admission_cycle))[0][0] or 0

		benefit = flt(total_benefit)
		self.scholarship_amount = benefit
		self.scholarship_applied = 1 if benefit > 0 else 0

	def calculate_totals(self):
		"""
		Sums all fee component rows to get the base total,
		then deducts scholarship_amount to compute final_payable_amount.
		"""
		base_total = 0
		for row in self.fee_components:
			if row.is_taxable:
				row.tax_amount = flt(row.amount) * flt(row.tax_rate) / 100
			else:
				row.tax_amount = 0
			row.total_amount = flt(row.amount) + flt(row.tax_amount)
			base_total += row.total_amount

		self.total_amount = base_total
		self.final_payable_amount = base_total - flt(self.scholarship_amount)

	def validate_status_change(self):
		if self.status == "Converted" and not self.fee_invoice:
			if not frappe.flags.in_test and not frappe.flags.in_import:
				frappe.throw(frappe._("Status cannot be set to 'Converted' manually. Please use the 'Create Invoice' action."))

	def before_submit(self):
		if not self.fee_components:
			frappe.throw(frappe._("At least one Fee Component is required."))

		for row in self.fee_components:
			if flt(row.amount) <= 0:
				frappe.throw(frappe._("Amount for {0} must be positive.").format(row.component_name or row.fee_component))

		self.status = "Assigned"

	def on_cancel(self):
		if self.fee_invoice:
			invoice = frappe.get_doc("Fee Invoice", self.fee_invoice)
			if flt(invoice.paid_amount) > 0:
				frappe.throw(frappe._("Cannot cancel Fee Assignment as payments have already been received for the linked Invoice {0}.").format(self.fee_invoice))

		self.status = "Cancelled"


def _get_academic_year_from_cycle(admission_cycle):
	"""
	Derive academic year name from the Admission Cycle's linked Admission Year.
	Falls back to None if not resolvable.
	"""
	if not admission_cycle:
		return None
	try:
		year_link = frappe.db.get_value("Admission Cycle", admission_cycle, "admission_year")
		if year_link:
			academic_year_name = frappe.db.get_value("Admission Year", year_link, "year_name")
			return academic_year_name or year_link
	except Exception:
		pass
	return None


def _map_applicant_to_student(student, applicant, program, admission_cycle, offer_letter_name=None):
	"""
	Central mapping function: Applicant fields → Student Master fields.
	All field assignments and error-safe lookups are handled here.
	"""

	# ── Registration / Naming ────────────────────────────────────────────────
	# name (registration_id) will be set via naming series — do not force-set here.
	# application_number tracks back to the Applicant record.
	student.application_number = applicant.name

	# ── Programme ────────────────────────────────────────────────────────────
	student.programme = program

	# ── Academic Year ────────────────────────────────────────────────────────
	# Priority: 1. Applicant's academic_year field, 2. Derived from Admission Cycle
	student.academic_year = applicant.get("academic_year")
	if not student.academic_year:
		derived_year = _get_academic_year_from_cycle(admission_cycle)
		if derived_year:
			student.academic_year = derived_year

	# ── Name: store full candidate_name in first_name only (no split) ─────────
	full_name = (applicant.get("candidate_name") or "").strip()
	student.first_name = full_name if full_name else (applicant.name or "Applicant")
	student.middle_name = None
	student.last_name = None

	# ── Personal Details ──────────────────────────────────────────────────────
	student.dob             = applicant.date_of_birth or nowdate()
	student.email           = applicant.email or ""
	student.personal_email  = applicant.email or ""
	student.phone           = applicant.mobile_number or applicant.get("alternate_contact") or ""
	student.alternate_phone = applicant.get("alternate_contact") if (
		applicant.get("alternate_contact") and applicant.mobile_number
	) else None
	student.nationality     = applicant.get("nationality") or None
	student.religion        = applicant.get("religion") or None

	# ── Gender (Link to Genders / Gender DocType) ─────────────────────────────
	raw_gender = applicant.get("gender")
	if raw_gender:
		if frappe.db.exists("Genders", raw_gender):
			student.gender = raw_gender
		elif frappe.db.exists("Gender", raw_gender):
			student.gender = raw_gender

	# ── Address ───────────────────────────────────────────────────────────────
	student.present_address   = applicant.get("correspondence_address") or None
	student.permanent_address = applicant.get("correspondence_address") or None
	student.city              = applicant.get("city") or None
	student.state             = applicant.get("state") or None
	student.pincode           = applicant.get("pincode") or None

	# ── PwD ───────────────────────────────────────────────────────────────────
	# Applicant stores "Yes"/"No" Select; Student Master uses Check (0/1)
	pwd_val = applicant.get("pwd")
	student.pwd = 1 if str(pwd_val).strip().lower() in ("yes", "1") else 0

	# ── Admission / Quota ─────────────────────────────────────────────────────
	# admission_type intentionally left blank per spec (leave as-is)
	# Map Quota based on reservation fields
	if str(applicant.get("ews")).strip() == "Yes":
		student.quota = "EWS"
	else:
		sc_st_obc = (applicant.get("whether_scstobc_ncl") or "").strip()
		if sc_st_obc == "OBC-NCL":
			student.quota = "OBC"
		elif sc_st_obc and sc_st_obc != "NA":
			student.quota = sc_st_obc
		else:
			student.quota = "General"

	# Set registration date
	student.date_of_registration = nowdate()

	# ── Class X ───────────────────────────────────────────────────────────────
	student.class_x_school          = applicant.get("class_x_school") or None
	student.class_x_percentage      = applicant.get("class_x_percentage") or None
	student.class_x_completion_year = applicant.get("class_x_year_of_completion") or None
	student.class_x_board           = applicant.get("class_x_board") or None
	student.class_x_max_cgpa        = applicant.get("class_x_cgpa") or None

	# ── Class XII ─────────────────────────────────────────────────────────────
	student.class_xii_school          = applicant.get("class_xii_school") or None
	student.class_xii_percentage      = applicant.get("hsc_percentage") or None
	student.class_xii_completion_year = applicant.get("class_xii_year_of_completion") or None
	student.class_xii_board           = applicant.get("class_xii_board") or None
	student.class_xii_max_cgpa        = applicant.get("class_xii_cgpa") or None
	student.class_xii_exam_name       = applicant.get("class_xii_name_of_examination") or None

	# ── Documents (Attachments) ───────────────────────────────────────────────
	student.passport_size_photo           = applicant.get("candidate_photo") or None
	student.aadhaar_card                  = applicant.get("id_proof") or None
	student.std_x_marksheet               = applicant.get("class_x_marksheet") or None
	student.class_xii_marksheet           = applicant.get("class_xii_marksheet") or None
	student.pwd_certificate               = applicant.get("pwd_certificate") or None
	student.entrance_exam_score_marksheet = applicant.get("national_test_certificate") or None

	if offer_letter_name:
		offer_pdf = frappe.db.get_value("Offer Letter", offer_letter_name, "offer_letter_pdf")
		if offer_pdf:
			student.offer_letter = offer_pdf

	# ── UG Degree (child table: ug_degree_details) ────────────────────────────
	student.ug_degree_completed = applicant.get("ug_degree_completion") or None
	if applicant.get("ug_degree_details"):
		for row in applicant.ug_degree_details:
			student.append("ug_degree_details", {
				"ug_program":    row.get("ug_program") or None,
				"college":        row.get("college") or None,
				"year_of_completion":row.get("year_of_completion") or None,
				"ug_cgpa":     row.get("ug_cgpa") or None,
				"ug_max_cgpa":       row.get("ug_max_cgpa") or None,
				"degree_certificate": row.get("degree_certificate") or None,
				"marksheets": row.get("marksheets") or None
			})

	# ── PG Degree (child table: pg_degree_details) ────────────────────────────
	if applicant.get("pg_degree_details"):
		for row in applicant.pg_degree_details:
			student.append("pg_degree_details", {
				"pg_program":    row.get("pg_program") or None,
				"collegeuniversity":        row.get("collegeuniversity") or None,
				"year_of_completion":row.get("year_of_completion") or None,
				"pg_cgpa":     row.get("pg_cgpa") or None,
				"pg_max_cgpa":       row.get("pg_max_cgpa") or None,
				"pg_degree_certificatebonafide_certificate_to_be_uploaded": row.get("pg_degree_certificatebonafide_certificate_to_be_uploaded") or None,
				"transcriptsmarksheets_to_be_uploaded": row.get("transcriptsmarksheets_to_be_uploaded") or None
			})

	# ── PhD ───────────────────────────────────────────────────────────────────
	student.phd_proposal      = applicant.get("phd_proposal") or None
	student.phd_programme     = applicant.get("phd_program_type") or None
	student.proposed_phd_topic = applicant.get("proposed_phd_topic") or None

	# ── Parents (child table) ─────────────────────────────────────────────────
	parent_rows = [
		{
			"relation": "Father",
			"name_field":       applicant.get("father_name"),
			"email_field":      applicant.get("father_email"),
			"mobile_field":     applicant.get("father_mobile"),
			"occupation_field": applicant.get("father_occupation"),
		},
		{
			"relation": "Mother",
			"name_field":       applicant.get("mother_name"),
			"email_field":      applicant.get("mother_email"),
			"mobile_field":     applicant.get("mother_mobile"),
			"occupation_field": applicant.get("mother_occupation"),
		},
	]

	guardian_required = str(applicant.get("guardian_required") or "").strip().lower()
	if guardian_required in ("yes", "1"):
		parent_rows.append({
			"relation": "Guardian",
			"name_field":       applicant.get("guardian_name"),
			"email_field":      applicant.get("guardian_email"),
			"mobile_field":     applicant.get("guardian_mobile"),
			"occupation_field": None,
		})

	for p in parent_rows:
		if p["name_field"]:   # only add row if at least a name exists
			student.append("parents", {
				"relation":   p["relation"],
				"first_name":  p["name_field"],
				"email":      p["email_field"] or None,
				"phone":     p["mobile_field"] or None,
				"occupation": p["occupation_field"] or None,
			})

	# ── Account Status (set at enrollment) ───────────────────────────────────
	student.student_status = "Active"
	student.account_status = "Active"

	return student


@frappe.whitelist()
def create_invoice(docname):
	doc = frappe.get_doc("Applicant Fee Assignment", docname)

	if doc.fee_type == "Application Fee":
		frappe.throw(frappe._("Create Invoice is only for Admission Fee assignments. Application Fee does not create Fee Invoice."))

	if doc.status != "Paid":
		frappe.throw(frappe._(
			"Invoice and conversion are only allowed when the fee has been paid. "
			"Current status is '{0}'. Please ensure payment is completed before converting to student."
		).format(doc.status or "unknown"))

	applicant = frappe.get_doc("Applicant", doc.applicant)

	# ── 1. Create Student Master if not exists ────────────────────────────────
	student_name = frappe.db.get_value("Student Master", {"application_number": applicant.name}, "name")

	if not student_name:
		try:
			student = frappe.new_doc("Student Master")

			# Map all Applicant fields → Student Master via central mapping function
			student = _map_applicant_to_student(student, applicant, doc.program, doc.admission_cycle, doc.offer_letter)

			student.insert(
				ignore_permissions=True,
				ignore_mandatory=True,
				ignore_links=True,
			)
			student_name = student.name

			frappe.logger().info(
				f"[create_invoice] Student Master created: {student_name} "
				f"for Applicant: {applicant.name} | AFA: {docname}"
			)

		except Exception as student_err:
			err_msg = (
				f"[create_invoice] Failed to create Student Master for Applicant '{applicant.name}' "
				f"(AFA: {docname}). Error: {str(student_err)}"
			)
			frappe.log_error(
				message=frappe.get_traceback(),
				title=f"Student Master Creation Failed | Applicant: {applicant.name}"
			)
			frappe.throw(frappe._(
				"Could not create Student record. Please check the Error Log for details. Error: {0}"
			).format(str(student_err)))

	# ── 2. Student Enrollment ─────────────────────────────────────────────────
	# enrollment_name = frappe.db.get_value(
	# 	"Student Enrollment",
	# 	{"student": student_name, "program": doc.program, "academic_year": doc.academic_year},
	# 	"name"
	# )

	# if not enrollment_name:
	# 	try:
	# 		enrollment = frappe.new_doc("Student Enrollment")
	# 		enrollment.student      = student_name
	# 		enrollment.program      = doc.program
	# 		enrollment.academic_year = doc.academic_year
	# 		enrollment.enrollment_date = nowdate()

	# 		cohort = frappe.db.get_value(
	# 			"Cohort",
	# 			{"program": doc.program, "academic_year": doc.academic_year},
	# 			"name"
	# 		)
	# 		if cohort:
	# 			enrollment.cohort = cohort

	# 		enrollment.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
	# 		enrollment_name = enrollment.name

	# 		frappe.logger().info(
	# 			f"[create_invoice] Student Enrollment created: {enrollment_name} "
	# 			f"| Student: {student_name} | AFA: {docname}"
	# 		)

	# 	except Exception as enroll_err:
	# 		frappe.log_error(
	# 			message=frappe.get_traceback(),
	# 			title=f"Student Enrollment Creation Failed | Student: {student_name}"
	# 		)
	# 		frappe.throw(frappe._(
	# 			"Could not create Student Enrollment record. "
	# 			"Please check the Error Log for details. Error: {0}"
	# 		).format(str(enroll_err)))

	# ── 3. Create Fee Invoice ─────────────────────────────────────────────────
	try:
		invoice = frappe.new_doc("Fee Invoice")
		invoice.student                = student_name
		invoice.enrollment             = enrollment_name
		invoice.program                = doc.program
		invoice.academic_year          = doc.academic_year
		invoice.invoice_date           = nowdate()
		invoice.due_date               = add_days(nowdate(), 15)
		invoice.applicant_fee_assignment = doc.name
		invoice.scholarship_amount     = doc.scholarship_amount

		for row in doc.fee_components:
			invoice.append("fee_components", {
				"fee_component":  row.fee_component,
				"component_name": row.component_name,
				"amount":         row.amount,
				"is_taxable":     row.is_taxable,
				"tax_rate":       row.tax_rate,
				"tax_amount":     row.tax_amount,
				"total_amount":   row.total_amount,
			})

		invoice.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		frappe.logger().info(
			f"[create_invoice] Fee Invoice created: {invoice.name} "
			f"| Student: {student_name} | AFA: {docname}"
		)

	except Exception as invoice_err:
		frappe.log_error(
			message=frappe.get_traceback(),
			title=f"Fee Invoice Creation Failed | Student: {student_name}"
		)
		frappe.throw(frappe._(
			"Could not create Fee Invoice. "
			"Please check the Error Log for details. Error: {0}"
		).format(str(invoice_err)))

	# ── 4. Migrate Payments if already paid as Applicant (Admission Fee only) ──
	if doc.status == "Paid" and doc.offer_letter:
		try:
			receipt_name = frappe.db.get_value(
				"Applicant Payment Receipt",
				{"offer_letter": doc.offer_letter, "docstatus": 1},
				"name"
			)

			if receipt_name:
				receipt = frappe.get_doc("Applicant Payment Receipt", receipt_name)

				payment = frappe.new_doc("Fee Payment")
				payment.student          = student_name
				payment.fee_invoice      = invoice.name
				payment.payment_date     = receipt.payment_date or nowdate()
				payment.payment_mode     = (
					receipt.payment_mode
					if receipt.payment_mode in ["Cash", "Bank Transfer", "Cheque", "Online Payment"]
					else "Other"
				)
				payment.amount           = receipt.total_amount
				payment.reference_number = receipt.transaction_id
				payment.status           = "Submitted"

				payment.insert(ignore_permissions=True)
				payment.submit()

				invoice.reload()
				invoice.save()

				frappe.logger().info(
					f"[create_invoice] Payment migrated from Receipt: {receipt_name} "
					f"| Fee Payment: {payment.name} | AFA: {docname}"
				)

		except Exception as payment_err:
			# Non-fatal: log and continue — invoice was already created successfully
			frappe.log_error(
				message=frappe.get_traceback(),
				title=f"Payment Migration Failed | Student: {student_name} | AFA: {docname}"
			)
			frappe.msgprint(
				frappe._(
					"Fee Invoice was created, but payment migration failed. "
					"Please reconcile manually. Error: {0}"
				).format(str(payment_err)),
				indicator="orange",
				alert=True,
			)

	# ── 5. Update Fee Assignment ──────────────────────────────────────────────
	doc.db_set("fee_invoice", invoice.name)
	doc.db_set("status", "Converted")

	# ── 6. Set Applicant status to Enrolled ───────────────────────────────────
	try:
		_enrolled_status = "Enrolled"
		if frappe.db.exists("Applicant Status", _enrolled_status):
			frappe.db.set_value(
				"Applicant", doc.applicant,
				"application_status", _enrolled_status,
				update_modified=True
			)
			frappe.db.commit()
	except Exception as status_err:
		# Non-fatal: student and invoice are already created; just log
		frappe.log_error(
			message=frappe.get_traceback(),
			title=f"Applicant Status Update Failed | Applicant: {doc.applicant} | AFA: {docname}"
		)

	return invoice.name


@frappe.whitelist()
def create_payment(docname, amount, payment_mode, reference_number=None):
	assignment = frappe.get_doc("Applicant Fee Assignment", docname)

	if not assignment.fee_invoice:
		frappe.throw(frappe._("Cannot create payment without a linked Fee Invoice. Please create the invoice first."))

	invoice = frappe.get_doc("Fee Invoice", assignment.fee_invoice)

	payment = frappe.new_doc("Fee Payment")
	payment.student          = invoice.student
	payment.fee_invoice      = invoice.name
	payment.payment_date     = nowdate()
	payment.payment_mode     = payment_mode
	payment.amount           = flt(amount)
	payment.reference_number = reference_number
	payment.status           = "Submitted"

	payment.insert(ignore_permissions=True)
	payment.submit()

	assignment.reload()
	invoice.reload()

	if invoice.status == "Paid":
		assignment.db_set("status", "Converted")
	elif invoice.status == "Partially Paid":
		assignment.db_set("status", "Partially Paid")

	return payment.name


# ── Bulk Convert to Student ───────────────────────────────────────────────────

@frappe.whitelist()
def bulk_convert_to_student(assignments):
	"""
	Convert multiple Applicant Fee Assignments to Student.
	Uses background job if batch > 10.
	"""
	if isinstance(assignments, str):
		assignments = json.loads(assignments)
	if not assignments:
		return {"message": frappe._("No assignments provided")}

	eligible = []
	for name in assignments:
		if not name:
			continue
		afa = frappe.db.get_value(
			"Applicant Fee Assignment",
			name,
			["fee_type", "status", "docstatus"],
			as_dict=True,
		)
		if not afa:
			continue
		if afa.fee_type != "Admission Fee" or afa.docstatus != 1:
			continue
		if afa.status != "Paid":
			continue
		eligible.append(name)

	if not eligible:
		return {
			"message": frappe._(
				"No eligible assignments to convert. "
				"Only assignments with status 'Paid' (fee payment completed) can be converted to student."
			)
		}

	if len(eligible) > 10:
		frappe.enqueue(
			method="slcm.admission.doctype.applicant_fee_assignment.applicant_fee_assignment.background_bulk_convert_worker",
			queue="long",
			assignments=eligible,
			user=frappe.session.user,
			now=frappe.flags.in_test,
		)
		return {
			"queued": True,
			"message": frappe._(
				"Large batch ({0} assignments). Processing in the background. "
				"You will be notified when finished."
			).format(len(eligible)),
		}

	return _process_bulk_convert_batch(eligible)


def _process_bulk_convert_batch(assignments):
	"""Process a list of AFA docnames; return { success: [], errors: [] }."""
	results = {"success": [], "errors": []}
	for docname in assignments:
		try:
			invoice_name = create_invoice(docname)
			results["success"].append({"assignment": docname, "invoice": invoice_name})
		except Exception as e:
			frappe.db.rollback()
			err_detail = str(e)
			results["errors"].append({"assignment": docname, "error": err_detail})
			frappe.log_error(
				message=frappe.get_traceback(),
				title=f"Bulk Convert to Student Error | AFA: {docname}"
			)
	return results


def background_bulk_convert_worker(assignments, user):
	"""Background worker for bulk convert; notifies user when done."""
	frappe.set_user(user)
	results = _process_bulk_convert_batch(assignments)
	success_count = len(results["success"])
	error_count   = len(results["errors"])

	summary_msg = frappe._("Successfully converted {0} applicants to students.").format(success_count)
	if error_count > 0:
		summary_msg += " " + frappe._("{0} errors encountered. Check the Error Log for details.").format(error_count)

	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
	enqueue_create_notification(
		[user],
		{
			"subject": frappe._("Bulk Convert to Student Report"),
			"email_content": (
				f"<h4>{summary_msg}</h4>"
				f"<p>{frappe._('Check Applicant Fee Assignment and Fee Invoice list for details.')}</p>"
			),
			"type": "Alert",
			"document_type": "Applicant Fee Assignment",
		},
	)
	frappe.publish_realtime(
		event="bulk_convert_to_student_done",
		message={"success": success_count, "errors": error_count},
		user=user,
	)