import json
import frappe
from frappe import _
from frappe.model.document import Document


@frappe.whitelist()
def create_merit_rule(program_offering, admission_cycle, programme_level,
					  rule_name, version, effective_from, effective_to, is_active, components):
	"""Create a Merit Rule and link it to the Program Offering."""
	if isinstance(components, str):
		components = json.loads(components)

	doc = frappe.new_doc("Merit Rule")
	doc.rule_name = rule_name
	doc.admission_cycle = admission_cycle
	doc.program_level = programme_level
	doc.version = int(version or 1)
	doc.effective_from = effective_from
	doc.effective_to = effective_to or None
	doc.is_active = int(is_active or 0)
	doc.approval_authority = "Admissions Committee"

	for comp in components:
		doc.append("components", {
			"component_type": comp.get("component_type"),
			"weight": float(comp.get("weight") or 0),
			"is_active": int(comp.get("is_active") or 1)
		})

	doc.insert(ignore_permissions=True)

	# Link back to the program offering
	frappe.db.set_value("Program Offering", program_offering, "merit_rule", doc.name)

	return doc.name


@frappe.whitelist()
def get_programs_for_matrix(doctype, txt, searchfield, start, page_len, filters):
	"""Returns programs linked to active Program Offerings for the given cycle and campus."""
	if not filters:
		return []
	
	admission_cycle = filters.get("admission_cycle")
	campus = filters.get("campus")
	
	if not admission_cycle or not campus:
		return []

	# Join with Program to get the name/title if needed, but here we just need the program link
	return frappe.db.sql("""
		SELECT DISTINCT program
		FROM `tabProgram Offering`
		WHERE admission_cycle = %s
		AND campus = %s
		AND is_active = 1
		AND program LIKE %s
		ORDER BY program ASC
		LIMIT %s, %s
	""", (admission_cycle, campus, f"%{txt}%", start, page_len))


class ProgramOffering(Document):

	def validate(self):
		self.validate_unique_offering()
		self.validate_programme_level_matches_cycle()
		self.validate_seat_counts()
		self.calculate_derived_seats()
		self.validate_campus_active()
		self.validate_cycle_not_closed()


	def calculate_derived_seats(self):
		if not self.is_reservation_applicable or not self.reservations:
			return
		for row in self.reservations:
			if row.reservation_percentage:
				row.seats = int((self.total_available_seats * row.reservation_percentage) / 100)

	def validate_seat_counts(self):
		if self.total_available_seats <= 0:
			frappe.throw(_("Total Available Seats must be greater than 0. Please set Government or Management Quota."))
		
		if self.is_reservation_applicable and self.reservations:
			total_res_seats = sum(row.seats or 0 for row in self.reservations)
			if total_res_seats > self.total_available_seats:
				frappe.throw(
					_("Total Reserved Seats ({0}) exceeds Total Available Seats ({1}).")
					.format(total_res_seats, self.total_available_seats)
				)

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

	# def on_update(self):
	# 	self.sync_with_admission_year()

	# def sync_with_admission_year(self):
	# 	"""Keep backward compatibility with Admission Year sync (refined)."""
	# 	admission_year_name = frappe.db.get_value(
	# 		"Admission Year", {"is_active": 1}, "name"
	# 	)
	# 	if not admission_year_name:
	# 		return

	# 	admission_year = frappe.get_doc("Admission Year", admission_year_name)
	# 	campus_to_match = self.campus
	# 	for row in admission_year.participating_campuses:
	# 		if row.campus == campus_to_match:
	# 			row.reservation_applied = self.is_reservation_applicable
	# 			row.is_active = self.is_available_for_admission
	# 			admission_year.save(ignore_permissions=True)
	# 			break