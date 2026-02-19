# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document



class MeritRuleMapping(Document):

	def validate(self):
		if not self.program_level:
			frappe.throw("Program Level is required for Merit Rule Mapping.")

		if self.is_active:
			# Allow multiple active mappings per campus+cycle, but NOT for the same program_level
			existing = frappe.get_all(
				"Merit Rule Mapping",
				filters={
					"admission_cycle": self.admission_cycle,
					"campus": self.campus,
					"program_level": self.program_level,
					"is_active": 1,
					"name": ["!=", self.name]
				}
			)

			if existing:
				frappe.throw(
					f"An active Merit Rule Mapping already exists for Admission Cycle '{self.admission_cycle}', "
					f"Campus '{self.campus}' and Program Level '{self.program_level}'. "
					f"Please deactivate the existing mapping before creating a new one."
				)

	def autoname(self):
		if not self.admission_cycle or not self.campus or not self.program_level:
			frappe.throw("Admission Cycle, Campus and Program Level are required for naming.")

		cycle = self.admission_cycle.replace(" ", "").upper()
		campus = self.campus.replace(" ", "").upper()
		level = self.program_level.upper()
		self.name = f"MRM-{cycle}-{campus}-{level}"