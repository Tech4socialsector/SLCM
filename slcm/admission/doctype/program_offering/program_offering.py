import frappe
from frappe import _
from frappe.model.document import Document

class ProgramOffering(Document):
	def validate(self):
		self.validate_capacity()
		self.validate_availability()
		self.validate_duplicate()

	def validate_capacity(self):
		if self.intake_capacity <= 0:
			frappe.throw(_("Intake Capacity must be greater than 0"))

	def validate_availability(self):
		if self.is_available_for_admission:
			# Cache campus and admission year
			campus = frappe.get_doc("Campus", self.campus)
			admission_year = frappe.get_doc("Admission Year", self.admission_year)

			# 1. Campus must be active
			if not campus.is_active:
				frappe.throw(_("Campus {0} is not active. Cannot enable Program Offering.").format(self.campus))

			# 2. Admission Year must be Open
			if admission_year.status != "Open":
				frappe.throw(_("Admission Year {0} is not Open. Current status: {1}").format(
					self.admission_year, admission_year.status
				))

			# 3. Campus must be part of Admission Year
			is_participating = any(c.campus == self.campus and c.is_active for c in admission_year.participating_campuses)
			if not is_participating:
				frappe.throw(_("Campus {0} is not a participating active campus for Admission Year {1}").format(
					self.campus, self.admission_year
				))

	def validate_duplicate(self):
		# Prevent duplicate program under same campus + admission year
		duplicate = frappe.db.exists("Program Offering", {
			"program_name": self.program_name,
			"campus": self.campus,
			"admission_year": self.admission_year,
			"name": ["!=", self.name]
		})
		if duplicate:
			frappe.throw(_("Program {0} is already offered at {1} for {2}").format(
				self.program_name, self.campus, self.admission_year
			))

	def before_save(self):
		# Cannot disable program if applications already submitted
		if not self.is_available_for_admission and not self.is_new():
			# Check if any applications exist for this program offering
			# Assuming Application doctype name is "Student Application" or similar, 
			# but requirements say "Application DocType"
			if frappe.db.exists("Student Application", {"program_offering": self.name}):
				frappe.throw(_("Cannot disable Program Offering {0} as applications have already been submitted").format(self.name))
