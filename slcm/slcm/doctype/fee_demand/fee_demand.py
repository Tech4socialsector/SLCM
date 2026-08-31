import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, today, now_datetime, getdate


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
		elif self.due_date and getdate(self.due_date) < getdate(today()) and outstanding > 0:
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
		self.check_permission("write")
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
			sm = frappe.db.get_value("Student Master", {"student": self.student}, "name")
			row = frappe.get_doc({
				"doctype":      "Student Fee Payment Log",
				"parent":       sm or self.student,
				"parenttype":   "Student Master",
				"parentfield":  "fee_payment_log",
				"event_type":   event,
				"timestamp":    now_datetime(),
				"amount":       abs(paid_delta),
				"fee_demand":   self.name,
				"to_status":    self.status,
				"triggered_by": frappe.session.user,
				"remarks":      f"Fee Demand: {self.name}",
			})
			row.insert(ignore_permissions=True)
		except Exception:
			pass


@frappe.whitelist()
def mark_dues_cleared(demand_names, payment_mode="Cash", remarks=None):
	"""
	Administrative "dues cleared" action for one or more Fee Demands.

	Records a real Fee Payment for each affected student's outstanding
	demands (grouped by student, since Fee Payment is per-student) and
	submits it, so the demand's status/outstanding, receipt generation,
	and payment logs all flow through the existing, already-validated
	payment pipeline instead of hand-editing amounts/status here.
	"""
	if isinstance(demand_names, str):
		demand_names = frappe.parse_json(demand_names)
	if not demand_names:
		frappe.throw(_("Please select at least one Fee Demand."))

	demands = frappe.get_all(
		"Fee Demand",
		filters={"name": ["in", demand_names]},
		fields=["name", "student", "description", "fee_component", "outstanding_amount", "status"],
	)
	if not demands:
		frappe.throw(_("No valid Fee Demand records found."))

	clearable = [
		d for d in demands
		if d.status not in ("Paid", "Cancelled", "Waived") and flt(d.outstanding_amount) > 0
	]
	skipped = [d.name for d in demands if d not in clearable]
	if not clearable:
		frappe.throw(_("None of the selected demands have an outstanding amount to clear."))

	by_student = {}
	for d in clearable:
		by_student.setdefault(d.student, []).append(d)

	created = []
	for student, rows in by_student.items():
		payment = frappe.new_doc("Fee Payment")
		payment.student = student
		payment.payment_date = today()
		payment.payment_mode = payment_mode
		payment.amount = sum(flt(r.outstanding_amount) for r in rows)
		payment.remarks = remarks or _("Dues marked cleared administratively.")
		for r in rows:
			payment.append("payment_demands", {
				"fee_demand": r.name,
				"demand_description": r.description or r.fee_component,
				"outstanding_amount": r.outstanding_amount,
				"amount_allocated": r.outstanding_amount,
			})
		payment.insert(ignore_permissions=True)
		payment.submit()
		created.append(payment.name)

	return {
		"created_payments": created,
		"cleared_demands": [d.name for d in clearable],
		"skipped_demands": skipped,
	}
