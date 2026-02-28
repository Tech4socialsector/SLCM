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
		self.validate_duplicate_mapping()
		self.validate_business_rules()

	def validate_duplicate_mapping(self):
		existing = frappe.db.exists(
			"Scholarship Scheme Mapping",
			{
				"scholarship_scheme": self.scholarship_scheme,
				"admission_cycle": self.admission_cycle,
				"program": self.program,
				"campus": self.campus,
				"category": self.category,
				"name": ["!=", self.name]
			}
		)

		if existing:
			frappe.throw(frappe._("Duplicate scholarship mapping exists."))

	def validate_business_rules(self):
		# Admission Cycle must be Active
		if self.admission_cycle:
			is_cycle_active = frappe.db.get_value("Admission Cycle", self.admission_cycle, "is_active")
			if not is_cycle_active:
				frappe.throw(frappe._("Admission Cycle {0} must be Active").format(self.admission_cycle))

		# Scholarship Scheme must be Active
		if self.scholarship_scheme:
			scheme_status = frappe.db.get_value("Scholarship Scheme", self.scholarship_scheme, "status")
			if scheme_status != "Active":
				frappe.throw(frappe._("Scholarship Scheme {0} must be Active (Current Status: {1})").format(
					self.scholarship_scheme, scheme_status
				))

from frappe.utils import flt
