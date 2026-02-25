import frappe
from frappe import _
from frappe.model.document import Document

class StageMaster(Document):
	def validate(self):
		self.validate_sequence_uniqueness()

	def validate_sequence_uniqueness(self):
		# Although marked as unique in JSON, explicit validation for better error message
		existing = frappe.db.get_value("Stage Master", {
			"sequence_number": self.sequence_number,
			"name": ["!=", self.name]
		}, "stage_name")
		if existing:
			frappe.throw(_("Sequence Number {0} is already assigned to {1}").format(self.sequence_number, existing))

	def on_trash(self):
		# Prevent deletion if linked to applications
		if frappe.db.exists("Applicant", {"current_stage": self.name}):
			frappe.throw(_("Cannot delete Stage Master {0} because it is linked to Admission Applications").format(self.name))
