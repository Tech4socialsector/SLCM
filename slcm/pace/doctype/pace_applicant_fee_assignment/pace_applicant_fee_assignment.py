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

	def on_payment_authorized(self, status):
		if status in ["Paid", "Completed"]:
			self.db_set("status", "Paid")
			# Check if receipt already exists by checking the linked PACE Receipt doctype
			if not frappe.db.exists("PACE Receipt", {"fee_assignment": self.name}):
				self.create_receipt()
			# Update application status
			if self.applicant:
				frappe.db.set_value("PACE Application", self.applicant, "status", "Submitted")
		elif status == "Failed":
			self.db_set("status", "Cancelled")

	def calculate_totals(self):
		total_amount = 0
		if self.fee_components:
			for row in self.fee_components:
				total_amount += row.total_amount
		else:
			# If no components, use the total_amount already set (useful for application fee)
			total_amount = self.total_amount
		
		self.total_amount = total_amount
		self.final_payable_amount = total_amount
