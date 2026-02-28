# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ScholarshipScheme(Document):
	def autoname(self):
		if not self.admission_cycle:
			frappe.throw(frappe._("Admission Cycle is mandatory for naming"))
		
		cycle_code = frappe.db.get_value("Admission Cycle", self.admission_cycle, "cycle_code")
		if not cycle_code:
			frappe.throw(frappe._("Cycle Code not found in Admission Cycle {0}").format(self.admission_cycle))
		
		# Naming Series: SS-{CYCLE}-{SCHEME_CODE}
		if not self.scheme_code:
			frappe.throw(frappe._("Scheme Code is mandatory for naming"))
			
		self.name = f"SS-{cycle_code}-{self.scheme_code}"
