import frappe
from frappe import _
from frappe.model.document import Document


class CampusSeatMatrix(Document):

	def validate(self):
		self.validate_unique_combination()
		self.validate_total_seats()
		self.validate_is_locked_changes()
		self.validate_cross_cycle()
		self.validate_seat_sum()

	def before_save(self):
		# Compute available_seats
		filled = self.filled_seats or 0
		self.available_seats = max(0, (self.total_seats or 0) - filled)
		# Ensure filled_seats and available_seats are read_only on save
		# (enforced in JSON and client script; server enforces via no-edit path)

	def validate_unique_combination(self):
		existing = frappe.db.get_value(
			"Campus Seat Matrix",
			{
				"admission_round": self.admission_round,
				"program_offering": self.program_offering,
				"reservation_category": self.reservation_category,
				"name": ["!=", self.name],
				"docstatus": ["!=", 2],
			},
			"name"
		)
		if existing:
			frappe.throw(
				_("A Campus Seat Matrix record already exists for the same Admission Round, Program Offering, and Reservation Category (record: {0}).")
				.format(existing)
			)

	def validate_total_seats(self):
		if self.total_seats is not None and self.total_seats <= 0:
			frappe.throw(_("Total Seats must be greater than 0."))

	def validate_is_locked_changes(self):
		if not self.is_locked or self.is_new():
			return
		old = self.get_doc_before_save()
		if not old:
			return
		if self.total_seats != old.total_seats:
			frappe.throw(
				_("Campus Seat Matrix is locked. Total Seats cannot be changed.")
			)
		if self.cut_off_score != old.cut_off_score:
			frappe.throw(
				_("Campus Seat Matrix is locked. Cut-Off Score cannot be changed.")
			)

	def validate_cross_cycle(self):
		"""Ensure the selected Admission Round belongs to the same cycle as the Program Offering."""
		if not self.admission_round or not self.program_offering:
			return
		round_cycle = frappe.db.get_value("Admission Round", self.admission_round, "admission_cycle")
		offering_cycle = frappe.db.get_value("Program Offering", self.program_offering, "admission_cycle")
		if round_cycle and offering_cycle and round_cycle != offering_cycle:
			frappe.throw(
				_("The selected Admission Round belongs to Cycle '{0}', but the Program Offering belongs to Cycle '{1}'. They must be from the same Admission Cycle.")
				.format(round_cycle, offering_cycle)
			)

	def validate_seat_sum(self):
		"""Sum of all CSM total_seats for same offering + round must equal Program Offering total_seats."""
		if not self.program_offering or not self.admission_round:
			return

		po_total = frappe.db.get_value("Program Offering", self.program_offering, "total_seats")
		if not po_total:
			return

		# Get all CSM records for same round+offering (excluding current if not new)
		filters = {
			"program_offering": self.program_offering,
			"admission_round": self.admission_round,
			"docstatus": ["!=", 2],
		}
		if not self.is_new():
			filters["name"] = ["!=", self.name]

		existing_sum = frappe.db.get_value(
			"Campus Seat Matrix",
			filters,
			"sum(total_seats)"
		) or 0

		new_total = existing_sum + (self.total_seats or 0)

		if new_total > po_total:
			frappe.throw(
				_("Total seats across all Reservation Category rows ({0}) exceeds Program Offering total seats ({1}). Reduce total_seats on this record.")
				.format(new_total, po_total)
			)
