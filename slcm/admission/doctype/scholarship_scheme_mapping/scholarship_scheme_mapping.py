# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname


class ScholarshipSchemeMapping(Document):
	def autoname(self):
		if not self.admission_cycle:
			frappe.throw(frappe._("Admission Cycle is mandatory for naming"))
		
		# Naming Series: SSM-{CYCLE}-.#####
		self.name = make_autoname(f"SSM-{self.admission_cycle}-.#####")

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
			cycle_status = frappe.db.get_value("Admission Cycle", self.admission_cycle, "status")
			if cycle_status != "Active":
				frappe.throw(frappe._("Admission Cycle {0} must be Active (Current Status: {1})").format(
					self.admission_cycle, cycle_status
				))

		# Scholarship Scheme must be Active
		if self.scholarship_scheme:
			scheme_status = frappe.db.get_value("Scholarship Scheme", self.scholarship_scheme, "status")
			if scheme_status != "Active":
				frappe.throw(frappe._("Scholarship Scheme {0} must be Active (Current Status: {1})").format(
					self.scholarship_scheme, scheme_status
				))

from frappe.utils import flt
