import frappe
from frappe.model.document import Document


class WaitlistRule(Document):
	def validate(self):
		self.validate_active_rule()

	def validate_active_rule(self):
		if (self.status or "").lower() == "active":
			# Check for other active rules for the same campus, program level and admission cycle
			existing_active_rule = frappe.db.get_value(
				"Waitlist Rule",
				{
					"campus": self.campus,
					"admission_cycle": self.admission_cycle,
					"program_level": self.program_level,
					"status": "Active",
					"name": ["!=", self.name]
				},
				"name"
			)

			if existing_active_rule:
				frappe.throw(
					frappe._("Another active Waitlist Rule ({0}) already exists for Campus '{1}', Program Level '{2}' and Admission Cycle '{3}'. Please deactivate it before activating this rule.").format(
						existing_active_rule, self.campus, self.program_level, self.admission_cycle
					),
					title=frappe._("Duplicate Active Rule")
				)
