# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

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
			# For Application Fee: get program and admission_cycle from Applicant
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
				metadata = frappe.db.get_value("Applicant", self.applicant, ["admission_cycle", "academic_year"], as_dict=True)
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

		# Sum all approved scholarship benefits for this applicant in this cycle
		total_benefit = frappe.db.sql("""
			SELECT SUM(calculated_benefit)
			FROM `tabScholarship Application`
			WHERE applicant_id = %s AND admission_cycle = %s AND status = 'Approved'
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


@frappe.whitelist()
def create_invoice(docname):
	doc = frappe.get_doc("Applicant Fee Assignment", docname)

	if doc.fee_type == "Application Fee":
		frappe.throw(frappe._("Create Invoice is only for Admission Fee assignments. Application Fee does not create Fee Invoice."))

	if doc.status not in ["Assigned", "Partially Paid", "Paid"]:
		frappe.throw(frappe._("Invoice can only be created for assignments with status 'Assigned', 'Partially Paid', or 'Paid'."))

	applicant = frappe.get_doc("Applicant", doc.applicant)

	# 1. Create Student Master if not exists
	student_name = frappe.db.get_value("Student Master", {"application_number": applicant.name}, "name")
	if not student_name:
		student = frappe.new_doc("Student Master")
		student.application_number = applicant.name
		student.first_name = applicant.candidate_name
		student.dob = applicant.date_of_birth or nowdate()
		student.email = applicant.email
		student.phone = applicant.mobile_number
		student.programme = doc.program

		if applicant.gender and frappe.db.exists("Gender", applicant.gender):
			student.gender = applicant.gender

		student.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
		student_name = student.name

	# 2. Student Enrollment
	enrollment_name = frappe.db.get_value("Student Enrollment",
		{"student": student_name, "program": doc.program, "academic_year": doc.academic_year}, "name")

	if not enrollment_name:
		enrollment = frappe.new_doc("Student Enrollment")
		enrollment.student = student_name
		enrollment.program = doc.program
		enrollment.academic_year = doc.academic_year
		enrollment.enrollment_date = nowdate()

		cohort = frappe.db.get_value("Cohort", {"program": doc.program, "academic_year": doc.academic_year}, "name")
		if cohort:
			enrollment.cohort = cohort

		enrollment.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
		enrollment_name = enrollment.name

	# 3. Create Fee Invoice
	invoice = frappe.new_doc("Fee Invoice")
	invoice.student = student_name
	invoice.enrollment = enrollment_name
	invoice.program = doc.program
	invoice.academic_year = doc.academic_year
	invoice.invoice_date = nowdate()
	invoice.due_date = add_days(nowdate(), 15)
	invoice.applicant_fee_assignment = doc.name

	for row in doc.fee_components:
		invoice.append("fee_components", {
			"fee_component": row.fee_component,
			"component_name": row.component_name,
			"amount": row.amount,
			"is_taxable": row.is_taxable,
			"tax_rate": row.tax_rate,
			"tax_amount": row.tax_amount,
			"total_amount": row.total_amount
		})

	invoice.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

	# 4. Migrate Payments if already paid as Applicant (Admission Fee only)
	if doc.status == "Paid" and doc.offer_letter:
		receipt_name = frappe.db.get_value("Applicant Payment Receipt",
			{"offer_letter": doc.offer_letter, "docstatus": 1}, "name")

		if receipt_name:
			receipt = frappe.get_doc("Applicant Payment Receipt", receipt_name)

			payment = frappe.new_doc("Fee Payment")
			payment.student = student_name
			payment.fee_invoice = invoice.name
			payment.payment_date = receipt.payment_date or nowdate()
			payment.payment_mode = receipt.payment_mode if receipt.payment_mode in ["Cash", "Bank Transfer", "Cheque", "Online Payment"] else "Other"
			payment.amount = receipt.total_amount
			payment.reference_number = receipt.transaction_id
			payment.status = "Submitted"

			payment.insert(ignore_permissions=True)
			payment.submit()

			invoice.reload()
			invoice.save()

	# 5. Update Fee Assignment
	doc.db_set("fee_invoice", invoice.name)
	doc.db_set("status", "Converted")

	return invoice.name


@frappe.whitelist()
def create_payment(docname, amount, payment_mode, reference_number=None):
	assignment = frappe.get_doc("Applicant Fee Assignment", docname)

	if not assignment.fee_invoice:
		frappe.throw(frappe._("Cannot create payment without a linked Fee Invoice. Please create the invoice first."))

	invoice = frappe.get_doc("Fee Invoice", assignment.fee_invoice)

	payment = frappe.new_doc("Fee Payment")
	payment.student = invoice.student
	payment.fee_invoice = invoice.name
	payment.payment_date = nowdate()
	payment.payment_mode = payment_mode
	payment.amount = flt(amount)
	payment.reference_number = reference_number
	payment.status = "Submitted"

	payment.insert(ignore_permissions=True)
	payment.submit()

	assignment.reload()
	invoice.reload()

	if invoice.status == "Paid":
		assignment.db_set("status", "Converted")
	elif invoice.status == "Partially Paid":
		assignment.db_set("status", "Partially Paid")

	return payment.name
