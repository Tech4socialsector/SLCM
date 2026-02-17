# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MeritRuleMapping(Document):
	def validate(self):
		if self.is_active:
			existing = frappe.get_all(
				"Merit Rule Mapping",
				filters={
					"admission_cycle": self.admission_cycle,
					"campus": self.campus,
					"is_active": 1,
					"name": ["!=", self.name]
				}
			)

			if existing:
				frappe.throw(
					f"Active mapping already exists for Admission Cycle '{self.admission_cycle}' "
					f"and Campus '{self.campus}'."
				)
	
	def autoname(self):
		if not self.admission_cycle or not self.campus:
			frappe.throw("Admission Cycle and Campus are required for naming.")

		cycle = self.admission_cycle.replace(" ", "").upper()
		campus = self.campus.replace(" ", "").upper()
		
		# Get count of existing mappings for this combination
		count = frappe.db.count("Merit Rule Mapping", {
			"admission_cycle": self.admission_cycle,
			"campus": self.campus
		})
		
		number = str(count + 1).zfill(2)
		self.name = f"MRM-{cycle}-{campus}-{number}"