import frappe
from frappe.model.document import Document

class PACEApplicantFeeAssignment(Document):
	def validate(self):
		self.calculate_totals()

	def on_update(self):
		if self.status == "Paid":
			self.create_receipt()

	def create_receipt(self):
		from slcm.pace.api import _create_pace_receipt
		receipt = _create_pace_receipt(self, self.get("transaction_id") or "Manual")
		if receipt:
			self.db_set("fee_receipt", receipt.name)

	def calculate_totals(self):
		total_amount = 0
		for row in self.fee_components:
			total_amount += row.total_amount
		
		self.total_amount = total_amount
		self.final_payable_amount = total_amount
