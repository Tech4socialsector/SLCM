import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


class FeeRefund(Document):

	def validate(self):
		self._validate_refund_amount()

	def on_submit(self):
		self._apply_refund()
		self.db_set("status", "Approved")
		self.db_set("approved_by", frappe.session.user)
		self.db_set("approved_on", today())

	def on_cancel(self):
		self._reverse_refund()
		self.db_set("status", "Reversed")

	def _validate_refund_amount(self):
		refund = flt(self.refund_amount)
		if refund <= 0:
			frappe.throw("Refund Amount must be greater than zero.")

		paid = flt(frappe.db.get_value("Fee Demand", self.fee_demand, "paid_amount"))
		if refund > paid:
			frappe.throw(
				f"Refund Amount (₹{refund:,.2f}) cannot exceed the amount already paid "
				f"(₹{paid:,.2f}) on demand {self.fee_demand}."
			)

		existing = frappe.db.exists(
			"Fee Refund",
			{
				"fee_demand": self.fee_demand,
				"status": "Approved",
				"name": ["!=", self.name],
			}
		)
		if existing:
			frappe.throw(
				f"Fee Demand {self.fee_demand} already has an approved refund ({existing}). "
				"Cancel it before creating a new one."
			)

	def _apply_refund(self):
		demand = frappe.get_doc("Fee Demand", self.fee_demand)

		if demand.status == "Cancelled":
			frappe.throw(f"Cannot process refund — Fee Demand {self.fee_demand} is Cancelled.")

		refund = flt(self.refund_amount)
		demand.paid_amount = max(0, flt(demand.paid_amount) - refund)
		demand.outstanding_amount = flt(demand.net_payable or demand.original_amount) - flt(demand.paid_amount) - flt(demand.credit_adjusted)

		if demand.outstanding_amount > 0 and demand.status == "Paid":
			demand.status = "Partially Paid"

		demand.save(ignore_permissions=True)

	def _reverse_refund(self):
		demand = frappe.get_doc("Fee Demand", self.fee_demand)

		refund = flt(self.refund_amount)
		demand.paid_amount = flt(demand.paid_amount) + refund
		demand.outstanding_amount = max(
			0,
			flt(demand.net_payable or demand.original_amount) - flt(demand.paid_amount) - flt(demand.credit_adjusted)
		)

		if demand.outstanding_amount == 0:
			demand.status = "Paid"

		demand.save(ignore_permissions=True)
