import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


class FeeConcession(Document):

	def validate(self):
		self._calculate_waiver_amount()
		self._validate_waiver_amount()

	def on_submit(self):
		self._apply_waiver()
		self.db_set("status", "Approved")
		self.db_set("approved_by", frappe.session.user)
		self.db_set("approved_on", today())

	def on_cancel(self):
		self._reverse_waiver()
		self.db_set("status", "Reversed")

	def _calculate_waiver_amount(self):
		original = flt(self.original_amount)
		value = flt(self.waiver_value)

		if self.waiver_mode == "Percentage":
			self.waiver_amount = round(original * value / 100, 2)
		else:
			self.waiver_amount = value

	def _validate_waiver_amount(self):
		original = flt(self.original_amount)
		waiver = flt(self.waiver_amount)

		if waiver <= 0:
			frappe.throw("Waiver Amount must be greater than zero.")

		if waiver > original:
			frappe.throw(
				f"Waiver Amount (₹{waiver:,.2f}) cannot exceed Original Amount (₹{original:,.2f})."
			)

		# Block if another active concession already covers this demand
		existing = frappe.db.exists(
			"Fee Concession",
			{
				"fee_demand": self.fee_demand,
				"status": "Approved",
				"name": ["!=", self.name],
			}
		)
		if existing:
			frappe.throw(
				f"Fee Demand {self.fee_demand} already has an approved concession ({existing}). "
				"Cancel it before applying a new one."
			)

	def _apply_waiver(self):
		demand = frappe.get_doc("Fee Demand", self.fee_demand)

		if demand.status in ("Paid", "Cancelled"):
			frappe.throw(
				f"Cannot apply waiver — Fee Demand {self.fee_demand} is already {demand.status}."
			)

		paid = flt(demand.paid_amount)
		original = flt(demand.original_amount)
		new_waiver = flt(self.waiver_amount)

		if new_waiver > (original - paid):
			frappe.throw(
				f"Waiver (₹{new_waiver:,.2f}) exceeds the unpaid balance "
				f"(₹{original - paid:,.2f}) on demand {self.fee_demand}."
			)

		demand.waiver_amount = new_waiver
		demand.net_payable = original - new_waiver
		demand.outstanding_amount = max(0, demand.net_payable - paid - flt(demand.credit_adjusted))

		if demand.outstanding_amount == 0 and paid == 0 and new_waiver == original:
			demand.status = "Waived"
		elif demand.outstanding_amount == 0:
			demand.status = "Paid"

		demand.save(ignore_permissions=True)

	def _reverse_waiver(self):
		demand = frappe.get_doc("Fee Demand", self.fee_demand)

		paid = flt(demand.paid_amount)
		original = flt(demand.original_amount)

		demand.waiver_amount = 0
		demand.net_payable = original
		demand.outstanding_amount = max(0, original - paid - flt(demand.credit_adjusted))

		if demand.outstanding_amount > 0:
			demand.status = "Pending"

		demand.save(ignore_permissions=True)
