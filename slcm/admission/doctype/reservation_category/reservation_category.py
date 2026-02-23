import frappe
from frappe import _
from frappe.model.document import Document


class ReservationCategory(Document):

	def validate(self):
		self.validate_category_code_unique()
		self.validate_reservation_pct()

	def validate_category_code_unique(self):
		existing = frappe.db.get_value(
			"Reservation Category",
			{"category_code": self.category_code, "name": ["!=", self.name]},
			"name"
		)
		if existing:
			frappe.throw(
				_("Category Code '{0}' already exists in record {1}. Category Code must be unique.")
				.format(self.category_code, existing)
			)

	def validate_reservation_pct(self):
		if self.reservation_pct is not None:
			if self.reservation_pct < 0 or self.reservation_pct > 100:
				frappe.throw(_("Reservation Percentage must be between 0 and 100."))

	def on_trash(self):
		if frappe.db.exists("Campus Seat Matrix", {"reservation_category": self.name}):
			frappe.throw(
				_("Cannot delete Reservation Category '{0}' as it is linked to one or more Campus Seat Matrix records.")
				.format(self.name)
			)
