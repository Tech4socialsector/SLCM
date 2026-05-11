# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
			

class MeritRuleMapping(Document):

	def validate(self):
		if not self.program_level:
			frappe.throw("Program Level is required for Merit Rule Mapping.")

		if self.is_active:
			# Allow multiple active mappings per campus+cycle, but NOT for the same program_level (+ program if set)
			mapping_filters = {
				"admission_cycle": self.admission_cycle,
				"campus": self.campus,
				"program_level": self.program_level,
				"is_active": 1,
				"name": ["!=", self.name]
			}
			if self.program:
				mapping_filters["program"] = self.program
			else:
				# If program is not set, we might need to check if there's an active one without program
				# To avoid conflict with level-wise mapping
				pass

			existing = frappe.get_all(
				"Merit Rule Mapping",
				filters=mapping_filters
			)

			if existing:
				prog_msg = f" and Program '{self.program}'" if self.program else ""
				frappe.throw(
					f"An active Merit Rule Mapping already exists for Admission Cycle '{self.admission_cycle}', "
					f"Campus '{self.campus}' and Program Level '{self.program_level}'{prog_msg}. "
					f"Please deactivate the existing mapping before creating a new one."
				)

	def autoname(self):
		if not self.admission_cycle or not self.campus or not self.program_level:
			frappe.throw("Admission Cycle, Campus and Program Level are required for naming.")

		cycle = self.admission_cycle.replace(" ", "").upper()
		campus = self.campus.replace(" ", "").upper()
		level = self.program_level.upper()
		
		if self.program:
			program_code = frappe.db.get_value("Program", self.program, "program_code") or self.program
			prog = program_code.replace(" ", "").upper()
			self.name = f"MRM-{cycle}-{campus}-{prog}"
		else:
			self.name = f"MRM-{cycle}-{campus}-{level}"