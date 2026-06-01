import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


class StudentCreditNote(Document):

	def validate(self):
		if flt(self.credit_amount) <= 0:
			frappe.throw("Credit Amount must be greater than zero.")

	def on_submit(self):
		self.db_set("available_credit", flt(self.credit_amount))
		self.db_set("used_credit", 0)
		self.db_set("status", "Active")

	def on_cancel(self):
		if flt(self.used_credit) > 0:
			frappe.throw(
				f"Cannot cancel — ₹{self.used_credit:,.2f} of this credit has already been applied. "
				"Reverse the adjustments first."
			)
		self.db_set("status", "Cancelled")
		self.db_set("available_credit", 0)

	@frappe.whitelist()
	def apply_credit_to_demand(self, fee_demand, amount):
		"""Apply credit from this note to a fee demand."""
		amount = flt(amount)
		available = flt(self.available_credit)

		if amount <= 0:
			frappe.throw("Amount to adjust must be greater than zero.")
		if amount > available:
			frappe.throw(
				f"Amount (₹{amount:,.2f}) exceeds available credit (₹{available:,.2f})."
			)

		demand = frappe.get_doc("Fee Demand", fee_demand)
		if demand.student != self.student:
			frappe.throw("This credit note belongs to a different student.")

		demand.credit_adjusted = flt(demand.credit_adjusted) + amount
		demand.outstanding_amount = max(
			0,
			flt(demand.net_payable or demand.original_amount) - flt(demand.paid_amount) - flt(demand.credit_adjusted)
		)
		if demand.outstanding_amount == 0:
			demand.status = "Paid"
		demand.save(ignore_permissions=True)

		new_available = available - amount
		new_used = flt(self.used_credit) + amount

		# Insert child row directly — avoids "cannot update after submit" error
		frappe.get_doc({
			"doctype": "Credit Adjustment Row",
			"parent": self.name,
			"parenttype": "Student Credit Note",
			"parentfield": "adjustments",
			"idx": len(self.adjustments) + 1,
			"fee_demand": fee_demand,
			"fee_component": demand.fee_component,
			"amount_adjusted": amount,
			"adjusted_on": today(),
			"adjusted_by": frappe.session.user,
		}).insert(ignore_permissions=True)

		self.db_set("available_credit", new_available)
		self.db_set("used_credit", new_used)
		if new_available == 0:
			self.db_set("status", "Exhausted")

		return {"available_credit": new_available, "used_credit": new_used}
