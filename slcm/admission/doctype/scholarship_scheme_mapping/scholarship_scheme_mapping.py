# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname


class ScholarshipSchemeMapping(Document):
	def autoname(self):
		if not self.admission_cycle:
			frappe.throw(frappe._("Admission Cycle is mandatory for naming"))
		
		cycle_code = frappe.db.get_value("Admission Cycle", self.admission_cycle, "cycle_code")
		if not cycle_code:
			frappe.throw(frappe._("Cycle Code not found in Admission Cycle {0}").format(self.admission_cycle))
		
		# Naming Series: SSM-{CYCLE}-.#####
		self.name = make_autoname(f"SSM-{cycle_code}-.#####")

	def validate(self):
		if self.min_income and self.max_income and flt(self.min_income) > flt(self.max_income):
			frappe.throw(frappe._("Minimum Income cannot be greater than Maximum Income"))

from frappe.utils import flt
