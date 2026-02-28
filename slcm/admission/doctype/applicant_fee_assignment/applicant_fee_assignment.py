# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, add_days, nowdate

class ApplicantFeeAssignment(Document):
	def validate(self):
		self.set_notification_receiver()
		self.calculate_totals()
		self.validate_status_change()

	def set_notification_receiver(self):
		if self.applicant:
			applicant_email = frappe.db.get_value("Applicant", self.applicant, "email")
			if applicant_email:
				user_name = frappe.db.get_value("User", {"email": applicant_email}, "name")
				if user_name:
					self.notification_receiver = user_name

	def calculate_totals(self):
		total_amount = 0
		for row in self.fee_components:
			# Calculate tax amount if taxable
			if row.is_taxable:
				row.tax_amount = flt(row.amount) * flt(row.tax_rate) / 100
			else:
				row.tax_amount = 0
			
			row.total_amount = flt(row.amount) + flt(row.tax_amount)
			total_amount += row.total_amount
		
		self.total_amount = total_amount

	def validate_status_change(self):
		if self.status == "Converted" and not self.fee_invoice:
			if not frappe.flags.in_test and not frappe.flags.in_import:
				frappe.throw(frappe._("Status cannot be set to 'Converted' manually. Please use the 'Create Invoice' action."))

	def before_submit(self):
		if not self.fee_components:
			frappe.throw(frappe._("At least one Fee Component is required."))
		
		for row in self.fee_components:
			if flt(row.amount) <= 0:
				frappe.throw(frappe._("Amount for {0} must be positive.").format(row.component_name))
		
		self.status = "Assigned"

	def on_cancel(self):
		if self.fee_invoice:
			# Check if invoice has payments
			invoice = frappe.get_doc("Fee Invoice", self.fee_invoice)
			if flt(invoice.paid_amount) > 0:
				frappe.throw(frappe._("Cannot cancel Fee Assignment as payments have already been received for the linked Invoice {0}.").format(self.fee_invoice))
			
			# If no payments, cancel the invoice too? 
			# Requirement says change status to Cancelled.
		
		self.status = "Cancelled"

@frappe.whitelist()
def create_invoice(docname):
	doc = frappe.get_doc("Applicant Fee Assignment", docname)
	
	if doc.status not in ["Assigned", "Partially Paid"]:
		frappe.throw(frappe._("Invoice can only be created for assignments with status 'Assigned' or 'Partially Paid'."))
	
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
		
		# For testing: Bypass missing Genders/Links
		if applicant.gender and frappe.db.exists("Gender", applicant.gender):
			student.gender = applicant.gender

		student.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
		student_name = student.name
	
	# 2. Student Enrollment
	# Try to find an existing enrollment for this program/year
	enrollment_name = frappe.db.get_value("Student Enrollment", 
		{"student": student_name, "program": doc.program, "academic_year": doc.academic_year}, "name")
	
	if not enrollment_name:
		enrollment = frappe.new_doc("Student Enrollment")
		enrollment.student = student_name
		enrollment.program = doc.program
		enrollment.academic_year = doc.academic_year
		enrollment.enrollment_date = nowdate()
		
		# Find a cohort, but don't fail if not found
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
	invoice.due_date = add_days(nowdate(), 15) # Configurable? Using 15 as per requirement
	invoice.fee_assignment = doc.name
	
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
	# invoice.submit() # Temporarily skipping submit to see if redirect works with Draft
	
	# 4. Update Fee Assignment
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
	
	# Status of Applicant Fee Assignment might need to be updated 
	# if we want to track Part Paid/Paid on the assignment itself.
	# But Converted usually implies it's handed off to the Finance module.
	# Let's check the invoice status and update assignment if needed.
	assignment.reload()
	invoice.reload()
	
	if invoice.status == "Paid":
		assignment.db_set("status", "Converted") 
	elif invoice.status == "Partially Paid":
		assignment.db_set("status", "Partially Paid")
	
	return payment.name
