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
		if paid <= 0:
			frappe.throw(
				f"Cannot create a refund for demand {self.fee_demand} — "
				"no payment has been made yet. Refunds are only allowed after "
				"the student has paid towards this demand."
			)
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
		demand = frappe.db.get_value(
			"Fee Demand", self.fee_demand,
			["status", "paid_amount", "refunded_amount", "net_payable",
			 "original_amount", "credit_adjusted", "outstanding_amount"],
			as_dict=True,
		)
		if not demand:
			frappe.throw(f"Fee Demand {self.fee_demand} not found.")
		if demand.status == "Cancelled":
			frappe.throw(f"Cannot process refund — Fee Demand {self.fee_demand} is Cancelled.")

		refund      = flt(self.refund_amount)
		new_paid    = max(0, flt(demand.paid_amount) - refund)
		new_refunded = flt(demand.refunded_amount) + refund
		net         = flt(demand.net_payable or demand.original_amount)
		new_outstanding = max(0, net - new_paid - flt(demand.credit_adjusted))

		new_status = demand.status
		if new_outstanding > 0 and demand.status == "Paid":
			new_status = "Partially Paid"
		elif new_outstanding > 0 and demand.status not in ("Partially Paid", "Overdue", "Waived", "Cancelled"):
			new_status = "Partially Paid"

		frappe.db.set_value("Fee Demand", self.fee_demand, {
			"paid_amount":       new_paid,
			"refunded_amount":   new_refunded,
			"outstanding_amount": new_outstanding,
			"status":            new_status,
		})

	def _reverse_refund(self):
		demand = frappe.db.get_value(
			"Fee Demand", self.fee_demand,
			["status", "paid_amount", "refunded_amount", "net_payable",
			 "original_amount", "credit_adjusted"],
			as_dict=True,
		)
		if not demand:
			return

		refund      = flt(self.refund_amount)
		new_paid    = flt(demand.paid_amount) + refund
		new_refunded = max(0, flt(demand.refunded_amount) - refund)
		net         = flt(demand.net_payable or demand.original_amount)
		new_outstanding = max(0, net - new_paid - flt(demand.credit_adjusted))

		new_status = demand.status
		if new_outstanding <= 0 and new_paid > 0:
			new_status = "Paid"
		elif new_paid > 0 and new_outstanding > 0:
			new_status = "Partially Paid"

		frappe.db.set_value("Fee Demand", self.fee_demand, {
			"paid_amount":       new_paid,
			"refunded_amount":   new_refunded,
			"outstanding_amount": new_outstanding,
			"status":            new_status,
		})
