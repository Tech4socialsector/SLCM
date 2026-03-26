import frappe
from frappe import _
from frappe.model.document import Document


class Campus(Document):
    pass

	# def validate(self):
	# 	self.validate_intake_capacity()

	# def validate_intake_capacity(self):
	# 	if self.intake_capacity and self.intake_capacity <= 0:
	# 		frappe.throw(_("Intake Capacity must be greater than 0."))

	# def on_update(self):
	# 	self.sync_with_admission_year()

	# def sync_with_admission_year(self):
	# 	admission_year_name = frappe.db.get_value(
	# 		"Admission Year",
	# 		{"is_active": 1},
	# 		"name"
	# 	)

	# 	if not admission_year_name:
	# 		return

	# 	admission_year = frappe.get_doc("Admission Year", admission_year_name)

	# 	current_academic_year = frappe.db.get_single_value(
	# 		"Admission Settings",
	# 		"current_academic_year"
	# 	)

	# 	if admission_year.academic_year != current_academic_year:
	# 		return

	# 	existing_row = None
	# 	for row in admission_year.participating_campuses:
	# 		if row.campus == self.name:
	# 			existing_row = row
	# 			break

	# 	if self.allow_admission:
	# 		if not existing_row:
	# 			admission_year.append("participating_campuses", {
	# 				"campus": self.name,
	# 				"is_active": 1
	# 			})
	# 			admission_year.save(ignore_permissions=True)
	# 	else:
	# 		if existing_row:
	# 			admission_year.participating_campuses.remove(existing_row)
	# 			admission_year.save(ignore_permissions=True)
