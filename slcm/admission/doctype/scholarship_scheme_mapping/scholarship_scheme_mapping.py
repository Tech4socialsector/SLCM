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

	@frappe.whitelist()
	def sync_count(self):
		"""
		Recalculates current_count based on approved scholarship applications.
		"""
		from slcm.admission.doctype.seat_allocation.seat_allocation import get_applicant_categories
		
		apps = frappe.get_all("Scholarship Application", filters={
			"scholarship_scheme": self.scholarship_scheme,
			"admission_cycle": self.admission_cycle,
			"campus": self.campus,
			"status": "Approved"
		}, fields=["name", "program", "applicant_id"])
		
		count = 0
		for app in apps:
			# Check program match
			program_match = not self.program or self.program == app.program
			
			# Check category match
			category_match = True
			if self.category:
				applicant_categories = get_applicant_categories(app.applicant_id)
				category_match = self.category in applicant_categories
				
			if program_match and category_match:
				count += 1
				
		self.db_set("current_count", count)
		return count

from frappe.utils import flt
