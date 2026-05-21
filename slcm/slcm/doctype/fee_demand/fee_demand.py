import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, today, now_datetime


class FeeDemand(Document):

	def validate(self):
		self._calculate_amounts()
		self._validate_waiver()
		self._auto_set_description()

	def before_save(self):
		self._update_status()

	def _calculate_amounts(self):
		self.original_amount = flt(self.original_amount)
		self.waiver_amount = flt(self.waiver_amount)
		self.paid_amount = flt(self.paid_amount)
		self.credit_adjusted = flt(self.credit_adjusted)

		self.net_payable = self.original_amount - self.waiver_amount
		self.outstanding_amount = self.net_payable - self.paid_amount - self.credit_adjusted

		# Prevent negative outstanding
		if self.outstanding_amount < 0:
			self.outstanding_amount = 0

	def _validate_waiver(self):
		if flt(self.waiver_amount) < 0:
			frappe.throw(_("Waiver Amount cannot be negative."))
		if flt(self.waiver_amount) > flt(self.original_amount):
			frappe.throw(
				_("Waiver Amount ({0}) cannot exceed Original Amount ({1}).").format(
					self.waiver_amount, self.original_amount
				)
			)

	def _auto_set_description(self):
		if not self.description and self.fee_component:
			self.description = self.fee_component

	def _update_status(self):
		# Full waiver → Waived
		if flt(self.waiver_amount) >= flt(self.original_amount) and flt(self.original_amount) > 0:
			self.status = "Waived"
			return

		# Already manually set to Cancelled or Waived — don't override
		if self.status in ("Cancelled", "Waived"):
			return

		outstanding = flt(self.outstanding_amount)
		paid = flt(self.paid_amount)

		if outstanding <= 0 and paid > 0:
			self.status = "Paid"
		elif paid > 0 and outstanding > 0:
			self.status = "Partially Paid"
		elif self.due_date and self.due_date < today() and outstanding > 0:
			self.status = "Overdue"
		else:
			if self.status not in ("Overdue",):
				self.status = "Pending"

	def update_payment_status(self, paid_delta, credit_delta=0):
		"""
		Called externally by Fee Payment on submit/cancel.
		paid_delta: positive on payment, negative on cancellation.
		credit_delta: positive when credit applied, negative when reversed.
		"""
		self.paid_amount = flt(self.paid_amount) + flt(paid_delta)
		self.credit_adjusted = flt(self.credit_adjusted) + flt(credit_delta)

		if self.paid_amount < 0:
			self.paid_amount = 0
		if self.credit_adjusted < 0:
			self.credit_adjusted = 0

		self._calculate_amounts()
		self._update_status()
		self.save(ignore_permissions=True)

		self._log_payment_event(paid_delta)

	@frappe.whitelist()
	def cancel_demand(self):
		"""Cancel this demand — only allowed if unpaid."""
		if self.status == "Paid":
			frappe.throw(_("Cannot cancel a fully paid Fee Demand."))
		if flt(self.paid_amount) > 0:
			frappe.throw(
				_("Cannot cancel a Fee Demand that has partial payments. "
				  "Please reverse the payment first.")
			)
		self.status = "Cancelled"
		self.save(ignore_permissions=True)
		return "Cancelled"

	def _log_payment_event(self, paid_delta):
		event = "Payment Recorded" if paid_delta > 0 else "Payment Reversed"
		try:
			frappe.get_doc({
				"doctype": "Student Fee Payment Log",
				"student": self.student,
				"event_type": event,
				"timestamp": now_datetime(),
				"amount": abs(paid_delta),
				"invoice": self.name,
				"to_status": self.status,
				"triggered_by": frappe.session.user,
			}).insert(ignore_permissions=True)
		except Exception:
			pass
