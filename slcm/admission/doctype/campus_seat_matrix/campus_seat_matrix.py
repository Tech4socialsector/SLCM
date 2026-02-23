import frappe
from frappe import _
from frappe.model.document import Document


class CampusSeatMatrix(Document):
	def validate(self):
		self.sync_total_seats_from_offering()
		self.calculate_total_seats()
		self.validate_sum_equals_total()

	def sync_total_seats_from_offering(self):
		if not all([self.admission_cycle, self.campus, self.program]):
			return
		
		po_intake = frappe.db.get_value(
			"Program Offering",
			{
				"admission_cycle": self.admission_cycle,
				"campus": self.campus,
				"program": self.program,
				"is_active": 1
			},
			"total_available_seats"
		)
		
		if po_intake is not None:
			self.total_seats = po_intake

	def calculate_total_seats(self):
		"""Calculates the sum of seats in the child table."""
		if not self.category_seats:
			return
		
		self.sum_of_category_seats = sum(row.seats or 0 for row in self.category_seats)

	def validate_sum_equals_total(self):
		if not self.total_seats:
			return
		
		attr_sum = getattr(self, "sum_of_category_seats", 0)
		if attr_sum != self.total_seats:
			frappe.throw(
				_("Total Seats in Category Breakdown ({0}) must equal the Program Offering intake ({1}).")
				.format(attr_sum, self.total_seats)
			)

	@frappe.whitelist()
	def fetch_seats_from_offering(self):
		"""Populates category_seats from Program Offering Reservations."""
		if not all([self.admission_cycle, self.campus, self.program]):
			frappe.throw(_("Admission Cycle, Campus, and Program are required."))

		po = frappe.db.get_value(
			"Program Offering",
			{
				"admission_cycle": self.admission_cycle,
				"campus": self.campus,
				"program": self.program,
				"is_active": 1
			},
			["name"],
			as_dict=1
		)

		if not po:
			frappe.throw(_("No active Program Offering found for the selected criteria."))

		po_doc = frappe.get_doc("Program Offering", po.name)
		self.category_seats = []
		
		for row in po_doc.reservations:
			# Skip if category is not a valid Reservation Category (link)
			if not row.category:
				continue
				
			self.append("category_seats", {
				"category": row.category,
				"seats": row.seats or 0
			})
		
		self.calculate_total_seats()
		return self
