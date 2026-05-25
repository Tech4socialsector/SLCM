# Copyright (c) 2025, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class FeePayment(Document):
	def validate(self):
		if self.fee_invoice:
			self.validate_payment_amount()
		# Validate multi-demand allocation if demands table is used
		if self.payment_demands:
			self._validate_demand_allocation()

	def on_submit(self):
		self.db_set("status", "Submitted", update_modified=False)
		if self.fee_invoice:
			self.update_fee_invoice()
		# Process multi-demand payments
		if self.payment_demands:
			self._apply_demand_payments()
		# Always create a receipt
		self._create_fee_receipt()

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
		if self.fee_invoice:
			self.update_fee_invoice(cancel=True)
		# Reverse multi-demand payments
		if self.payment_demands:
			self._reverse_demand_payments()
		# Cancel linked receipt
		self._cancel_fee_receipt()

	def _validate_demand_allocation(self):
		total_allocated = sum(flt(row.amount_allocated) for row in self.payment_demands)
		if round(total_allocated, 2) != round(flt(self.amount), 2):
			frappe.throw(
				_("Total allocated amount ({0}) must equal the payment amount ({1}). "
				  "Please adjust the amounts in the Fee Demands table.").format(
					frappe.utils.fmt_money(total_allocated, currency="INR"),
					frappe.utils.fmt_money(flt(self.amount), currency="INR"),
				)
			)
		for row in self.payment_demands:
			if flt(row.amount_allocated) <= 0:
				frappe.throw(
					_("Row {0}: Amount Allocated must be greater than zero.").format(row.idx)
				)
			outstanding = frappe.db.get_value("Fee Demand", row.fee_demand, "outstanding_amount") or 0
			if flt(row.amount_allocated) > flt(outstanding):
				frappe.throw(
					_("Row {0}: Amount Allocated ({1}) exceeds outstanding amount ({2}) "
					  "for demand <b>{3}</b>.").format(
						row.idx,
						frappe.utils.fmt_money(row.amount_allocated, currency="INR"),
						frappe.utils.fmt_money(outstanding, currency="INR"),
						row.fee_demand,
					)
				)

	def _apply_demand_payments(self):
		for row in self.payment_demands:
			demand = frappe.get_doc("Fee Demand", row.fee_demand)
			demand.update_payment_status(paid_delta=flt(row.amount_allocated))

	def _reverse_demand_payments(self):
		for row in self.payment_demands:
			try:
				demand = frappe.get_doc("Fee Demand", row.fee_demand)
				demand.update_payment_status(paid_delta=-flt(row.amount_allocated))
			except Exception:
				frappe.log_error(frappe.get_traceback(), f"FeePayment: failed to reverse demand {row.fee_demand}")

	def _create_fee_receipt(self):
		student = frappe.db.get_value(
			"Student Master", self.student,
			["registration_id", "first_name", "last_name", "programme", "academic_year", "year_of_study"],
			as_dict=True
		) or {}

		receipt = frappe.get_doc({
			"doctype": "Fee Receipt",
			"student": self.student,
			"student_name": student.get("first_name", ""),
			"registration_id": student.get("registration_id", ""),
			"programme": student.get("programme", ""),
			"academic_year": student.get("academic_year", ""),
			"year_of_study": student.get("year_of_study", ""),
			"fee_payment": self.name,
			"receipt_date": self.payment_date,
			"amount": self.amount,
			"payment_mode": self.payment_mode,
			"bank_account": self.bank_account,
			"reference_number": self.reference_number,
			"received_by": frappe.session.user,
			"demands_paid": [
				{
					"fee_demand": row.fee_demand,
					"description": row.demand_description or row.fee_demand,
					"amount": row.amount_allocated,
				}
				for row in (self.payment_demands or [])
			],
		})
		receipt.insert(ignore_permissions=True)
		self.db_set("receipt", receipt.name, update_modified=False)

	def _cancel_fee_receipt(self):
		if self.receipt:
			try:
				receipt_doc = frappe.get_doc("Fee Receipt", self.receipt)
				if receipt_doc.docstatus == 1:
					receipt_doc.cancel()
				else:
					receipt_doc.db_set("status", "Cancelled")
			except Exception:
				frappe.log_error(frappe.get_traceback(), "FeePayment: failed to cancel receipt")

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
