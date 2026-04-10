import frappe
from frappe.model.document import Document

class PACEApplicantFeeAssignment(Document):
	def validate(self):
		self.calculate_totals()

	def calculate_totals(self):
		total_amount = 0
		for row in self.fee_components:
			total_amount += row.total_amount
		
		self.total_amount = total_amount
		self.final_payable_amount = total_amount
