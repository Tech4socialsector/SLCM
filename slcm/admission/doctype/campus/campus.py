import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet

class Campus(NestedSet):
	nsm_parent_field = "parent_campus"

	def validate(self):
		# super(Campus, self).validate()
		self.validate_disabling()
		self.validate_circular_parent()

	def on_trash(self):
		super(Campus, self).on_trash()
		self.validate_deletion()

	def validate_disabling(self):
		if not self.is_active:
			# Prevent disabling campus if active program offering exists
			if frappe.db.exists("Program Offering", {"campus": self.name, "is_available_for_admission": 1}):
				frappe.throw(_("Cannot disable Campus {0} because it has active Program Offerings").format(self.name))

	def validate_circular_parent(self):
		if self.parent_campus == self.name:
			frappe.throw(_("Campus {0} cannot be its own parent").format(self.name))

	def validate_deletion(self):
		# Prevent deletion if child campuses exist
		if frappe.db.exists("Campus", {"parent_campus": self.name}):
			frappe.throw(_("Cannot delete Campus {0} because it has child campuses").format(self.name))
		
		# Prevent deletion if program offerings exist
		if frappe.db.exists("Program Offering", {"campus": self.name}):
			frappe.throw(_("Cannot delete Campus {0} because it is linked to Program Offerings").format(self.name))

	def on_update(self):
		super(Campus, self).on_update()
		# Rebuild tree if needed
		# NestedSet handles most of this
		pass