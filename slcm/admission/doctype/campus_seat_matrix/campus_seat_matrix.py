import frappe
from frappe import _
from frappe.model.document import Document


class CampusSeatMatrix(Document):
	def validate(self):
		self.calculate_total_seats()

	def calculate_total_seats(self):
		if not self.category_seats:
			self.total_seats = 0
			return
		
		self.total_seats = sum(row.seats or 0 for row in self.category_seats)
