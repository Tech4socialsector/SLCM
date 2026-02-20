import frappe
from frappe import _
from frappe.model.document import Document


class ProgramOffering(Document):

	def validate(self):
		self.validate_unique_offering()
		self.validate_programme_level_matches_cycle()
		self.validate_seat_counts()
		self.validate_campus_active()
		self.validate_cycle_not_closed()

	def validate_unique_offering(self):
		existing = frappe.db.get_value(
			"Program Offering",
			{
				"admission_cycle": self.admission_cycle,
				"campus": self.campus,
				"program": self.program,
				"name": ["!=", self.name],
			},
			"name"
		)
		if existing:
			frappe.throw(
				_("A Program Offering already exists for Admission Cycle '{0}', Campus '{1}', and Program '{2}' (record: {3}).")
				.format(self.admission_cycle, self.campus, self.program, existing)
			)

	def validate_programme_level_matches_cycle(self):
		if not self.admission_cycle or not self.programme_level:
			return
		cycle_level = frappe.db.get_value("Admission Cycle", self.admission_cycle, "programme_level")
		if cycle_level and cycle_level != self.programme_level:
			frappe.throw(
				_("Programme Level '{0}' does not match the Admission Cycle's level '{1}'.")
				.format(self.programme_level, cycle_level)
			)

	def validate_seat_counts(self):
		if self.total_seats is not None and self.total_seats <= 0:
			frappe.throw(_("Total Seats must be greater than 0."))
		if self.open_seats is not None and self.total_seats is not None:
			if self.open_seats > self.total_seats:
				frappe.throw(
					_("Open Category Seats ({0}) cannot exceed Total Seats ({1}).")
					.format(self.open_seats, self.total_seats)
				)

	def validate_campus_active(self):
		if not self.campus:
			return
		is_active = frappe.db.get_value("Campus", self.campus, "is_active")
		if not is_active:
			frappe.throw(
				_("Campus '{0}' is not active. Please select an active Campus for Program Offering.")
				.format(self.campus)
			)

	def validate_cycle_not_closed(self):
		if not self.admission_cycle:
			return
		cycle_status = frappe.db.get_value("Admission Cycle", self.admission_cycle, "status")
		if cycle_status == "Closed":
			frappe.throw(
				_("Cannot create a Program Offering for a Closed Admission Cycle '{0}'.")
				.format(self.admission_cycle)
			)

	def on_trash(self):
		if frappe.db.exists("Campus Seat Matrix", {"program_offering": self.name}):
			frappe.throw(
				_("Cannot delete Program Offering '{0}' as it is linked to one or more Campus Seat Matrix records.")
				.format(self.name)
			)

	def before_save(self):
		if not self.is_available_for_admission and not self.is_new():
			if frappe.db.exists("Student Application", {"program_offering": self.name}):
				frappe.throw(
					_("Cannot disable Program Offering '{0}' as applications have already been submitted.")
					.format(self.name)
				)

	def on_update(self):
		self.sync_with_admission_year()

	def sync_with_admission_year(self):
		"""Keep backward compatibility with Admission Year sync."""
		admission_year_name = frappe.db.get_value(
			"Admission Year", {"is_active": 1}, "name"
		)
		if not admission_year_name:
			return

		admission_year = frappe.get_doc("Admission Year", admission_year_name)

		current_academic_year = frappe.db.get_single_value(
			"Admission Settings", "current_academic_year"
		)

		if admission_year.academic_year != current_academic_year:
			return

		campus_to_match = self.campus
		for row in admission_year.participating_campuses:
			if row.campus == campus_to_match:
				row.eligibility_criteria = self.eligibility_based
				row.entrence_test = self.need_entrence_test
				row.schedule_interview = self.interview_required
				row.merit_list = self.merit_list
				row.offer_scholarship = self.scholarship_applicable
				row.reservation_applied = self.is_reservation_applicable
				row.is_active = self.is_available_for_admission
				admission_year.save(ignore_permissions=True)
				break