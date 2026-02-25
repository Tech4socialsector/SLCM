# Copyright (c) 2025, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate


class FeeInvoice(Document):
	def validate(self):
		self.calculate_amounts()
		self.update_status()

	def calculate_amounts(self):
		# Calculate total from components
		total = 0
		for row in self.fee_components:
			# If total_amount isn't set, calculate it now
			if not row.total_amount:
				if row.is_taxable:
					row.tax_amount = flt(row.amount) * flt(row.tax_rate) / 100
				else:
					row.tax_amount = 0
				row.total_amount = flt(row.amount) + flt(row.tax_amount)
			
			total += flt(row.total_amount)
		
		self.total_amount = total

		# Calculate paid amount from payments
		paid = 0
		for payment in self.payments:
			paid += flt(payment.amount)
		self.paid_amount = paid

		self.outstanding_amount = flt(self.total_amount) - flt(self.paid_amount)

	def update_status(self):
		if self.outstanding_amount <= 0:
			self.status = "Paid"
		elif self.paid_amount > 0:
			self.status = "Partially Paid"
		else:
			self.status = "Unpaid"

		# Check if overdue
		if self.due_date and getdate(nowdate()) > getdate(self.due_date) and self.status != "Paid":
			self.status = "Overdue"

	def on_update_after_submit(self):
		# Update fee assignment when payment is made
		if self.fee_assignment:
			# Check if it's a Student Fee Assignment or Applicant Fee Assignment
			assignment_doctype = "Student Fee Assignment"
			if not frappe.db.exists("Student Fee Assignment", self.fee_assignment):
				if frappe.db.exists("Applicant Fee Assignment", self.fee_assignment):
					assignment_doctype = "Applicant Fee Assignment"
				else:
					return

			assignment = frappe.get_doc(assignment_doctype, self.fee_assignment)
			
			if assignment_doctype == "Student Fee Assignment":
				assignment.paid_amount = self.paid_amount
				assignment.outstanding_amount = self.outstanding_amount
				assignment.update_status()
				assignment.save()
			else:
				# Applicant Fee Assignment
				if self.status == "Paid":
					assignment.status = "Converted" # Or maintain Converted if already set
				elif self.status == "Partially Paid":
					assignment.status = "Partially Paid"
				assignment.save()

	def on_payment_authorized(self, payment_status):
		"""Called by the payments app after a successful transaction."""
		if payment_status in ("Authorized", "Completed"):
			# Create Fee Payment
			payment = frappe.get_doc(
				{
					"doctype": "Fee Payment",
					"fee_invoice": self.name,
					"student": self.student,
					"amount": self.outstanding_amount,  # Or the amount from the log
					"payment_date": frappe.utils.today(),
					"payment_mode": "Online",
				}
			)
			payment.insert(ignore_permissions=True)
			payment.submit()

			# Update Log (if successful)
			log_entry = frappe.get_all(
				"Online Payment Log",
				filters={"fee_invoice": self.name, "status": "Pending"},
				limit=1,
				order_by="creation desc",
			)
			if log_entry:
				frappe.db.set_value("Online Payment Log", log_entry[0].name, "status", "Success")

	def get_payment_details(self):
		"""Returns details for the payment gateway."""
		return {
			"amount": self.outstanding_amount,
			"title": _("Fee Payment for {0}").format(self.name),
			"description": _("Payment for Student: {0}").format(self.student_name),
			"reference_doctype": self.doctype,
			"reference_docname": self.name,
			"payer_email": frappe.db.get_value("Student Master", self.student, "email"),
			"payer_name": self.student_name,
			"currency": "INR",  # Adjust as needed
		}

	@frappe.whitelist()
	def initiate_online_payment(self):
		"""
		Logs the attempt and returns the checkout URL.
		Handles gateway resolution server-side to avoid permission issues.
		"""
		self.flags.ignore_links = True
		self.save(ignore_permissions=True) # Ensure amounts are calculated
		gateway = frappe.db.get_value("Payment Gateway", {}, "name")
		if not gateway:
			frappe.throw(_("No Payment Gateway configured in the system."))

		# Create Log
		log = frappe.get_doc({
			"doctype": "Online Payment Log",
			"fee_invoice": self.name,
			"gateway": gateway,
			"amount": self.outstanding_amount,
			"status": "Pending"
		})
		log.insert(ignore_permissions=True)

		# Get Checkout URL
		from payments.utils.utils import get_checkout_url
		return get_checkout_url(
			payment_gateway=gateway,
			amount=self.outstanding_amount,
			reference_doctype=self.doctype,
			reference_docname=self.name,
			currency="INR" # Adjust as needed
		)
