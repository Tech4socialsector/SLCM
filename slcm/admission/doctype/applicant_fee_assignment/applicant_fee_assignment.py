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
		Admission Fee assignments DO apply scholarship; scholarship applies only to Admission Fee.
		"""
		if self.fee_type != "Admission Fee" or not self.applicant or not self.admission_cycle:
			return

		scholarship_data = frappe.db.get_all("Scholarship Application",
			filters={
				"applicant_id": self.applicant,
				"admission_cycle": self.admission_cycle,
				"status": "Approved"
			},
			fields=["name", "calculated_benefit"],
			order_by="creation desc"
		)

		total_benefit = sum(flt(d.calculated_benefit) for d in scholarship_data)
		self.scholarship_amount = total_benefit
		self.scholarship_applied = 1 if total_benefit > 0 else 0

		if scholarship_data and not self.scholarship_application:
			self.scholarship_application = scholarship_data[0].name

	def calculate_totals(self):
		"""
		Sum fee component rows (Admission Fee and Application Fee both use the child table).
		Scholarship is deducted only for Application Fee assignments.
		Mirrors ``application_fee`` from the grid total for Application Fee type.
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
		if self.fee_type == "Application Fee":
			self.application_fee = base_total
			
		self.final_payable_amount = max(0, base_total - flt(self.scholarship_amount))

	def validate_status_change(self):
		if self.status == "Converted" and not self.fee_invoice:
			if not frappe.flags.in_test and not frappe.flags.in_import:
				frappe.throw(frappe._("Status cannot be set to 'Converted' manually. Please use the 'Create Invoice' action."))

	def before_submit(self):
		if not self.fee_components:
			frappe.throw(frappe._("At least one Fee Component row is required."))

		for row in self.fee_components:
			if flt(row.amount) < 0:
				frappe.throw(
					frappe._("Amount for {0} cannot be negative.").format(
						row.component_name or row.fee_component
					)
				)
			if self.fee_type == "Admission Fee" and flt(row.amount) <= 0:
				frappe.throw(
					frappe._("Amount for {0} must be positive.").format(
						row.component_name or row.fee_component
					)
				)

		self.status = "Assigned"

	def on_cancel(self):
		if self.fee_invoice:
			invoice = frappe.get_doc("Fee Invoice", self.fee_invoice)
			if flt(invoice.paid_amount) > 0:
				frappe.throw(frappe._("Cannot cancel Fee Assignment as payments have already been received for the linked Invoice {0}.").format(self.fee_invoice))

		self.status = "Cancelled"


# ── Import unified conversion helpers ────────────────────────────────────────
# The field mapping, scholarship sync, and student creation logic now live in
# slcm/api/service/applicant_to_student.py to avoid duplication between
# the AFA doctype and the Applicant doctype (which also has a bulk-convert path).
from slcm.api.service.applicant_to_student import (
	_get_academic_year_from_cycle,
	_sync_finance_to_student,
	_sync_scholarship_to_student,
	convert_applicant_to_student,
)


def _map_applicant_to_student(student, applicant, program, admission_cycle, offer_letter_name=None):
	"""
	Forwarding stub — real implementation is in slcm.api.service.applicant_to_student.
	Kept for backward-compat with any direct callers within this module.
	"""
	from slcm.api.service.applicant_to_student import _map_applicant_to_student as _real_map
	return _real_map(student, applicant, program, admission_cycle, offer_letter_name)


@frappe.whitelist()
def create_invoice(docname, email_template=None, email_account=None):
	doc = frappe.get_doc("Applicant Fee Assignment", docname)

	if doc.fee_type == "Application Fee":
		frappe.throw(frappe._("Create Invoice is only for Admission Fee assignments. Application Fee does not create Fee Invoice."))

	if doc.status == "Converted":
		frappe.throw(frappe._("This assignment has already been converted to a student."))

	if doc.status not in ("Paid", "Partially Paid"):
		frappe.throw(frappe._(
			"Conversion is only allowed when status is 'Paid' or 'Partially Paid'. "
			"Current status is '{0}'."
		).format(doc.status or "unknown"))

	applicant = frappe.get_doc("Applicant", doc.applicant)

	# ── 1. Create Student Master via unified API (deduplication + role update included) ──
	result = convert_applicant_to_student(
		applicant_name=doc.applicant,
		program=doc.program,
		admission_cycle=doc.admission_cycle,
		offer_letter_name=doc.offer_letter,
	)
	student_name = result["student_name"]

	if result.get("created"):
		frappe.logger().info(
			f"[create_invoice] Student Master created: {student_name} "
			f"for Applicant: {applicant.name} | AFA: {docname}"
		)
	else:
		frappe.logger().info(
			f"[create_invoice] Re-using existing Student Master: {student_name} "
			f"for Applicant: {applicant.name} | AFA: {docname}"
		)

	# ── 2. Student Enrollment (optional on Fee Invoice; cohort drives Program / Academic Year) ──
	enrollment_name = None
	existing_enr = frappe.get_all(
		"Student Enrollment",
		filters={
			"student": student_name,
			"program": doc.program,
			"academic_year": doc.academic_year,
		},
		pluck="name",
		limit=1,
	)
	if existing_enr:
		enrollment_name = existing_enr[0]

	cohort = None
	if doc.program and doc.academic_year:
		cohort = frappe.db.get_value(
			"Cohort",
			{"program": doc.program, "academic_year": doc.academic_year},
			"name",
		)

	if not enrollment_name and cohort:
		try:
			enrollment = frappe.new_doc("Student Enrollment")
			enrollment.student = student_name
			enrollment.cohort = cohort
			enrollment.enrollment_date = nowdate()
			enrollment.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
			enrollment_name = enrollment.name

			frappe.logger().info(
				f"[create_invoice] Student Enrollment created: {enrollment_name} "
				f"| Student: {student_name} | AFA: {docname}"
			)

		except Exception as enroll_err:
			frappe.log_error(
				message=frappe.get_traceback(),
				title=f"Student Enrollment Creation Failed | Student: {student_name}",
			)
			frappe.throw(
				frappe._(
					"Could not create Student Enrollment record. "
					"Please check the Error Log for details. Error: {0}"
				).format(str(enroll_err))
			)
	elif not enrollment_name:
		frappe.throw(
			frappe._(
				"Cannot convert to student: no Cohort exists for Program '{0}' and Academic Year '{1}'. "
				"Create a Cohort for this program and year before converting (Student Enrollment is required)."
			).format(doc.program or "—", doc.academic_year or "—")
		)

	# ── 3. Create Fee Invoice ─────────────────────────────────────────────────
	try:
		invoice = frappe.new_doc("Fee Invoice")
		invoice.student = student_name
		invoice.enrollment = enrollment_name
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

		# ── Sync Finance tab of Student Master (Scholarship Details + Fee Details) ──
		# Always called after invoice creation so that the portal hero card
		# and Finance tab show accurate fee totals, scholarship info, and status.
		# Non-fatal — invoice was created successfully regardless.
		#
		# Note on fields:
		#   Fetching additional details from the linked Scholarship Application if present.
		
		scholarship_type = None
		scholarship_percentage = 0
		scholarship_approval_date = None
		
		if doc.get("scholarship_application"):
			sa_data = frappe.db.get_value("Scholarship Application", doc.scholarship_application, 
				["scholarship_scheme", "approval_date"], as_dict=True)
			if sa_data:
				scholarship_approval_date = sa_data.approval_date
				if sa_data.scholarship_scheme:
					scheme_data = frappe.db.get_value("Scholarship Scheme", sa_data.scholarship_scheme, 
						["scheme_type", "coverage_type", "coverage_value"], as_dict=True)
					if scheme_data:
						scholarship_type = scheme_data.scheme_type
						if scheme_data.coverage_type == "Percentage":
							scholarship_percentage = scheme_data.coverage_value

		_sync_finance_to_student(
			student_name=student_name,
			scholarship_amount=flt(doc.scholarship_amount),
			scholarship_type=scholarship_type,
			scholarship_percentage=flt(scholarship_percentage),
			scholarship_approval_date=scholarship_approval_date,
			# AFA.remarks maps to fee_waiver_remarks when a scholarship/waiver is applied
			fee_waiver_remarks=doc.get("remarks") or None,
			total_amount=flt(doc.total_amount),
			final_payable_amount=flt(doc.get("final_payable_amount") or 0),
			fee_payment_status=doc.status,
			fee_structure=doc.get("fee_structure") or None,
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
				# Use net_amount (after scholarship deduction) as the actual amount paid
				payment.amount           = flt(receipt.net_amount) if flt(receipt.get('net_amount')) > 0 else flt(receipt.total_amount)
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

	# NOTE: User role swap (Applicant → Student) is handled inside
	# convert_applicant_to_student() called in step 1 above.

	if student_name and doc.applicant:
		try:
			send_admission_notifications(student_name, doc.applicant, email_template, email_account)
		except Exception as notify_err:
			frappe.log_error(
				message=frappe.get_traceback(),
				title=f"Notification Dispatch Error | Student: {student_name} | Applicant: {doc.applicant}",
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

def ensure_default_email_template():
	template_name = "Student Admission Confirmation"
	if not frappe.db.exists("Email Template", template_name):
		doc = frappe.new_doc("Email Template")
		doc.name = template_name
		doc.use_html = 1
		doc.subject = "Admission Confirmation — Welcome to National Law School!"
		doc.response = """
<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
    <div style="text-align: center; margin-bottom: 20px;">
        <h2 style="color: #1a365d; margin: 0;">National Law School</h2>
        <p style="font-size: 14px; color: #718096; margin: 5px 0 0 0;">Admission Office</p>
    </div>
    
    <hr style="border: 0; border-top: 1px solid #e2e8f0; margin-bottom: 20px;">
    
    <p>Dear <strong>{{ candidate_name }}</strong>,</p>
    
    <p>Congratulations! We are pleased to inform you that your admission to the <strong>{{ program }}</strong> program for the Academic Year <strong>{{ academic_year }}</strong> at National Law School has been confirmed.</p>
    
    <div style="background-color: #f7fafc; border-left: 4px solid #3182ce; padding: 15px; margin: 20px 0; border-radius: 4px;">
        <p style="margin: 0 0 8px 0; font-size: 14px; color: #4a5568;">Your enrollment details are as follows:</p>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
            <tr>
                <td style="padding: 4px 0; color: #718096; width: 40%;">Student ID:</td>
                <td style="padding: 4px 0; font-weight: bold; color: #2d3748;">{{ student_id }}</td>
            </tr>
            <tr>
                <td style="padding: 4px 0; color: #718096;">Program:</td>
                <td style="padding: 4px 0; font-weight: bold; color: #2d3748;">{{ program }}</td>
            </tr>
            <tr>
                <td style="padding: 4px 0; color: #718096;">Academic Year:</td>
                <td style="padding: 4px 0; font-weight: bold; color: #2d3748;">{{ academic_year }}</td>
            </tr>
        </table>
    </div>
    
    <p>You can now log in to the <strong>Student Portal</strong> using your registered email address (<strong>{{ email }}</strong>) to view your course details, schedules, and fee invoices.</p>
    
    <p style="margin-top: 30px; font-size: 14px; color: #718096;">
        Warm regards,<br>
        <strong>Admissions Office</strong><br>
        National Law School
    </p>
</div>
"""
		doc.insert(ignore_permissions=True)
		frappe.db.commit()


def send_admission_notifications(student_name, applicant_name, email_template_name, email_account_name):
	if not applicant_name or not frappe.db.exists("Applicant", applicant_name):
		return

	# Force creation of default template if it doesn't exist
	ensure_default_email_template()

	applicant = frappe.get_doc("Applicant", applicant_name)
	if not applicant.email:
		return

	# Load Email Template
	if not email_template_name:
		email_template_name = "Student Admission Confirmation"
	
	if frappe.db.exists("Email Template", email_template_name):
		template = frappe.get_doc("Email Template", email_template_name)
		subject_template = template.subject or "Admission Confirmation — Welcome to National Law School!"
		body_template = template.response or ""
	else:
		# Fallback to defaults
		subject_template = "Admission Confirmation — Welcome to National Law School!"
		body_template = "<p>Your admission to {{ program }} is confirmed. Student ID: {{ student_id }}</p>"

	context = {
		"candidate_name": applicant.candidate_name or applicant_name,
		"program": applicant.program or "Program",
		"academic_year": applicant.academic_year or "Academic Year",
		"student_id": student_name,
		"email": applicant.email
	}

	# Render email
	subject = frappe.render_template(subject_template, context)
	content = frappe.render_template(body_template, context)

	sender_email = None
	if email_account_name:
		sender_email = frappe.db.get_value("Email Account", email_account_name, "email_id")

	# Send Email (Enqueued to Email Queue table)
	frappe.sendmail(
		recipients=[applicant.email],
		sender=sender_email,
		subject=subject,
		content=content,
		now=False
	)

	# Send System Notification
	if frappe.db.exists("User", applicant.email):
		from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
		enqueue_create_notification(
			[applicant.email],
			{
				"subject": subject,
				"email_content": f"Congratulations! Your admission to the {applicant.program} program is confirmed. Your Student ID is {student_name}.",
				"type": "Alert",
				"document_type": "Student Master",
				"document_name": student_name
			}
		)


@frappe.whitelist()
def bulk_convert_to_student(assignments, email_template=None, email_account=None):
	"""
	Convert multiple Applicant Fee Assignments to Student.
	Uses background job if batch > 250.
	"""
	if isinstance(assignments, str):
		assignments = json.loads(assignments)
	if not assignments:
		return {"message": frappe._("No assignments provided")}

	eligible = []
	skipped = []
	for name in assignments:
		if not name:
			continue
		afa = frappe.db.get_value(
			"Applicant Fee Assignment",
			name,
			["fee_type", "status", "docstatus", "name"],
			as_dict=True,
		)
		if not afa:
			skipped.append({"assignment": name, "reason": frappe._("Not found")})
			continue
		if afa.fee_type != "Admission Fee" or afa.docstatus != 1:
			skipped.append(
				{
					"assignment": name,
					"reason": frappe._("Must be submitted Admission Fee assignment."),
				}
			)
			continue
		if afa.status not in ("Paid", "Partially Paid"):
			skipped.append(
				{
					"assignment": name,
					"reason": frappe._(
						"Status must be 'Paid' or 'Partially Paid' (current: {0})."
					).format(afa.status or "—"),
				}
			)
			continue
		eligible.append(name)

	if not eligible:
		return {
			"message": frappe._(
				"No eligible assignments to convert. Only submitted Admission Fee rows with status "
				"'Paid' or 'Partially Paid' can be converted."
			),
			"skipped": skipped,
		}

	# Background queue for large batches (isolated commits + notification)
	if len(eligible) > 250:
		frappe.enqueue(
			method="slcm.admission.doctype.applicant_fee_assignment.applicant_fee_assignment.background_bulk_convert_worker",
			queue="long",
			assignments=eligible,
			user=frappe.session.user,
			email_template=email_template,
			email_account=email_account,
			timeout=3600,
			now=frappe.flags.in_test,
		)
		return {
			"queued": True,
			"message": frappe._(
				"Large batch detected ({0} assignments). Processing started safely in the background. "
				"You will receive a notification when finished."
			).format(len(eligible)),
			"skipped": skipped,
		}

	out = _process_bulk_convert_batch(eligible, email_template=email_template, email_account=email_account)
	if skipped:
		out["skipped"] = skipped
	return out


def _process_bulk_convert_batch(assignments, progress_user=None, email_template=None, email_account=None):
	"""Process a list of AFA docnames; return { success: [], errors: [] }. Commits each success separately."""
	results = {"success": [], "errors": []}
	total = len(assignments)
	for idx, docname in enumerate(assignments):
		if progress_user:
			frappe.publish_realtime(
				"bulk_convert_to_student_progress",
				{
					"progress": idx + 1,
					"total": total,
					"message": frappe._("Converting {0} ({1} / {2})").format(docname, idx + 1, total),
				},
				user=progress_user,
			)
		try:
			invoice_name = create_invoice(docname, email_template=email_template, email_account=email_account)
			frappe.db.commit()
			results["success"].append({"assignment": docname, "invoice": invoice_name})
		except Exception as e:
			frappe.db.rollback()
			err_detail = str(e)
			results["errors"].append({"assignment": docname, "error": err_detail})
			frappe.log_error(
				message=frappe.get_traceback(),
				title=f"Bulk Convert to Student Error | AFA: {docname}",
			)
	return results


def background_bulk_convert_worker(assignments, user, email_template=None, email_account=None):
	"""Background worker for bulk convert; notifies user when done."""
	frappe.set_user(user)
	results = _process_bulk_convert_batch(assignments, progress_user=user, email_template=email_template, email_account=email_account)
	success_count = len(results["success"])
	error_count = len(results["errors"])

	if error_count:
		summary_raw = frappe._("Converted {0} assignment(s); {1} failed.").format(success_count, error_count)
	else:
		summary_raw = frappe._("Successfully converted {0} assignment(s).").format(success_count)
	summary_msg = frappe.utils.escape_html(summary_raw)
	detail_lines = []
	for err in results["errors"][:25]:
		detail_lines.append(
			"<p><b>{0}</b>: {1}</p>".format(
				frappe.utils.escape_html(err.get("assignment") or ""),
				frappe.utils.escape_html(err.get("error") or ""),
			)
		)
	if len(results["errors"]) > 25:
		detail_lines.append(
			"<p><i>"
			+ frappe.utils.escape_html(
				frappe._("…and {0} more (see Error Log).").format(len(results["errors"]) - 25)
			)
			+ "</i></p>"
		)
	err_block = "".join(detail_lines)

	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	enqueue_create_notification(
		[user],
		{
			"subject": frappe._("Bulk Convert to Student — {0} ok, {1} errors").format(success_count, error_count),
			"email_content": (
				f"<h4>{summary_msg}</h4>"
				f"<p>{frappe.utils.escape_html(frappe._('Check Applicant Fee Assignment and Fee Invoice for details.'))}</p>"
				+ (f"<h5>{frappe.utils.escape_html(frappe._('Errors'))}</h5>{err_block}" if err_block else "")
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