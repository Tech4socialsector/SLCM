import frappe
from frappe import _
from frappe.model.document import Document

class Campus(Document):

	def on_update(self):
		self.sync_with_admission_year()

	def sync_with_admission_year(self):
		admission_year_name = frappe.db.get_value(
			"Admission Year",
			{"is_active": 1},
			"name"
		)

		if not admission_year_name:
			return

		admission_year = frappe.get_doc("Admission Year", admission_year_name)

		current_academic_year = frappe.db.get_single_value(
			"Admission Settings",
			"current_academic_year"
		)

		if admission_year.academic_year != current_academic_year:
			frappe.throw(
				_("Admission Year {0} is not the current academic year.")
				.format(admission_year.academic_year)
			)

		existing_row = None
		for row in admission_year.participating_campuses:
			if row.campus == self.name:
				existing_row = row
				break

		if self.allow_admission:
			if not existing_row:
				admission_year.append("participating_campuses", {
					"campus": self.name,
					"is_active": 1
				})
				admission_year.save()

		else:
			if existing_row:
				admission_year.participating_campuses.remove(existing_row)
				admission_year.save()

	# def validate(self):
	# 	# super(Campus, self).validate()
	# 	self.validate_disabling()
	# 	self.validate_circular_parent()

	# def on_trash(self):
	# 	super(Campus, self).on_trash()
	# 	self.validate_deletion()

	# def validate_disabling(self):
	# 	if not self.is_active:
	# 		# Prevent disabling campus if active program offering exists
	# 		if frappe.db.exists("Program Offering", {"campus": self.name, "is_available_for_admission": 1}):
	# 			frappe.throw(_("Cannot disable Campus {0} because it has active Program Offerings").format(self.name))

	# def validate_circular_parent(self):
	# 	if self.parent_campus == self.name:
	# 		frappe.throw(_("Campus {0} cannot be its own parent").format(self.name))

	# def validate_deletion(self):
	# 	# Prevent deletion if child campuses exist
	# 	if frappe.db.exists("Campus", {"parent_campus": self.name}):
	# 		frappe.throw(_("Cannot delete Campus {0} because it has child campuses").format(self.name))
		
	# 	# Prevent deletion if program offerings exist
	# 	if frappe.db.exists("Program Offering", {"campus": self.name}):
	# 		frappe.throw(_("Cannot delete Campus {0} because it is linked to Program Offerings").format(self.name))

	# def on_update(self):
	# 	super(Campus, self).on_update()
	# 	# Rebuild tree if needed
	# 	# NestedSet handles most of this
	# 	pass
