# Copyright (c) 2025, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FeePayment(Document):
	def validate(self):
		if self.fee_invoice:
			self.validate_payment_amount()

	def on_submit(self):
		self.update_fee_invoice()

	def on_cancel(self):
		self.update_fee_invoice(cancel=True)

	def validate_payment_amount(self):
		"""Validate that payment amount doesn't exceed outstanding amount"""
		invoice = frappe.get_doc("Fee Invoice", self.fee_invoice)

		# Get existing payments for this invoice
		existing_payments = frappe.db.sql(
			"""
			SELECT SUM(amount) as total
			FROM `tabFee Payment`
			WHERE fee_invoice = %s
			AND docstatus = 1
			AND name != %s
		""",
			(self.fee_invoice, self.name),
			as_dict=True,
		)

		paid_amount = (existing_payments[0].total or 0) if existing_payments else 0
		# Use final_payable_amount (after scholarship) as the ceiling, not total_amount.
		# total_amount is the gross fee before any scholarship deduction, so using it
		# would allow payments beyond what the student actually owes.
		outstanding = invoice.final_payable_amount - paid_amount

		if self.amount > outstanding:
			frappe.throw(
				_("Payment amount ({0}) cannot exceed outstanding amount ({1})").format(
					self.amount, outstanding
				)
			)

	def update_fee_invoice(self, cancel=False):
		"""Update fee invoice with payment"""
		invoice = frappe.get_doc("Fee Invoice", self.fee_invoice)

		# Add or remove payment entry
		if cancel:
			# Remove payment entry
			invoice.payments = [p for p in invoice.payments if p.payment != self.name]
		else:
			# Add payment entry if not exists
			payment_exists = False
			for payment in invoice.payments:
				if payment.payment == self.name:
					payment.amount = self.amount
					payment.payment_date = self.payment_date
					payment.payment_mode = self.payment_mode
					payment_exists = True
					break

			if not payment_exists:
				invoice.append(
					"payments",
					{
						"payment": self.name,
						"amount": self.amount,
						"payment_date": self.payment_date,
						"payment_mode": self.payment_mode,
					},
				)

		invoice.save(ignore_permissions=True)
		invoice.reload()
		self._sync_student_master()

	def _sync_student_master(self):
		"""Aggregate paid/outstanding across all invoices and update Student Master fields."""
		student = getattr(self, "student", None) or frappe.db.get_value(
			"Fee Invoice", self.fee_invoice, "student"
		)
		if not student:
			return
		try:
			row = frappe.db.sql(
				"""
				SELECT
					COALESCE(SUM(GREATEST(paid_amount, 0)), 0)        AS total_paid,
					COALESCE(SUM(GREATEST(outstanding_amount, 0)), 0) AS total_outstanding
				FROM `tabFee Invoice`
				WHERE student = %s
				""",
				student,
				as_dict=True,
			)[0]
			total_paid        = frappe.utils.flt(row.total_paid or 0)
			total_outstanding = frappe.utils.flt(row.total_outstanding or 0)

			if total_outstanding <= 0 and total_paid > 0:
				status = "Paid"
			elif total_paid > 0:
				status = "Partially Paid"
			else:
				status = "Unpaid"

			prev_status = frappe.db.get_value("Student Master", student, "fee_payment_status") or "Unpaid"
			frappe.db.set_value(
				"Student Master", student,
				{
					"total_paid_amount":   total_paid,
					"outstanding_balance": total_outstanding,
					"fee_payment_status":  status,
				},
				update_modified=False,
			)

			# Rebuild the fee_invoices child table so admin can see updated invoice rows
			from slcm.slcm.doctype.student_master.student_master import (
				_rebuild_fee_invoices,
				_append_payment_log,
			)
			sm_doc = frappe.get_doc("Student Master", student, ignore_permissions=True)
			_rebuild_fee_invoices(sm_doc)

			_append_payment_log(
				student,
				"Payment Recorded",
				amount=total_paid,
				invoice=self.fee_invoice,
				payment_mode=getattr(self, "payment_mode", "") or "",
				from_status=prev_status,
				to_status=status,
				remarks=(
					f"Total paid: ₹{total_paid:,.0f} · Outstanding: ₹{total_outstanding:,.0f}"
				),
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "FeePayment._sync_student_master failed")
