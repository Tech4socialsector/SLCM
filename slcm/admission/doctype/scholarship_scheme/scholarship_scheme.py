# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, getdate, today


class ScholarshipScheme(Document):
	def validate(self):
		self.validate_dates()
		self.validate_numeric_fields()
		self.validate_income_range()
		self.validate_merit_score()
		self.validate_coverage()
		self.validate_limits()
		self.validate_max_amount()

	def validate_numeric_fields(self):
		numeric_fields = ["min_income", "max_income", "coverage_value", "max_amount", "total_budget", "min_merit_score"]
		for field in numeric_fields:
			val = self.get(field)
			if val is not None and val != "":
				try:
					self.set(field, flt(val))
				except (ValueError, TypeError):
					frappe.throw(frappe._("Field {0} must be a number").format(self.meta.get_label(field)))

	def validate_dates(self):
		if self.application_start:
			if getdate(self.application_start) < getdate(today()):
				frappe.throw(frappe._("Application Start date cannot be in the past"))

		if self.application_start and self.application_end:
			if getdate(self.application_end) < getdate(self.application_start):
				frappe.throw(frappe._("Application End must be on or after Application Start"))

	def validate_income_range(self):
		if self.scheme_type == "Need":
			if self.min_income is None:
				frappe.throw(frappe._("Minimum Income is mandatory for Need scheme"))
			if self.max_income is None:
				frappe.throw(frappe._("Maximum Income is mandatory for Need scheme"))
		
		min_income = self.get("min_income")
		max_income = self.get("max_income")
		if min_income is not None and max_income is not None:
			if max_income < min_income:
				frappe.throw(frappe._("Maximum Income cannot be less than Minimum Income"))

	def validate_merit_score(self):
		if self.scheme_type == "Merit" and not self.min_merit_score:
			frappe.throw(frappe._("Minimum Merit Score is mandatory for Merit scheme"))
		
		if self.min_merit_score and (flt(self.min_merit_score) < 0 or flt(self.min_merit_score) > 100):
			frappe.throw(frappe._("Merit score must be between 0 and 100"))

	def validate_coverage(self):
		coverage_type = self.get("coverage_type")
		
		if coverage_type in ["Percentage", "Fixed"]:
			coverage_value = self.get("coverage_value")
			if coverage_value is None or coverage_value == "":
				frappe.throw(frappe._("Coverage Value is mandatory for {0}").format(coverage_type))
			
			val = flt(coverage_value)
			if val < 0:
				frappe.throw(frappe._("Coverage Value cannot be negative"))
			if coverage_type == "Percentage" and val > 100:
				frappe.throw(frappe._("Percentage cannot exceed 100%"))

		elif coverage_type == "Component-wise":
			if not self.get("coverage_rules"):
				frappe.throw(frappe._("Coverage Rules table is mandatory for Component-wise coverage"))
			
			for row in self.get("coverage_rules"):
				if row.coverage_type == "Percentage" and flt(row.coverage_value) > 100:
					frappe.throw(frappe._("Row #{0}: Percentage cannot exceed 100%").format(row.idx))
				if flt(row.coverage_value) < 0:
					frappe.throw(frappe._("Row #{0}: Coverage Value cannot be negative").format(row.idx))

	def validate_limits(self):
		max_beneficiaries = self.get("max_beneficiaries")
		current_beneficiaries = self.get("current_beneficiaries") or 0
		if max_beneficiaries and current_beneficiaries > max_beneficiaries:
			frappe.throw(frappe._("Current beneficiaries cannot exceed maximum limit"))

		total_budget = self.get("total_budget")
		utilized_budget = self.get("utilized_budget") or 0
		if total_budget and utilized_budget > total_budget:
			frappe.throw(frappe._("Utilized budget cannot exceed total budget"))

	def validate_max_amount(self):
		if self.coverage_type == "Percentage" and self.max_amount:
			if flt(self.max_amount) < 0:
				frappe.throw(frappe._("Maximum amount cannot be negative"))

	@frappe.whitelist()
	def sync_budget(self):
		"""
		Recalculates utilized_budget and current_beneficiaries based on approved applications.
		Useful for correcting discrepancies.
		"""
		result = frappe.db.sql("""
			SELECT count(name), sum(calculated_benefit)
			FROM `tabScholarship Application`
			WHERE scholarship_scheme = %s AND status = 'Approved'
		""", (self.name,))
		
		count, total = result[0] if result else (0, 0)

		self.current_beneficiaries = count or 0
		self.utilized_budget = flt(total or 0)
		
		status = self.status
		# Re-verify status based on limits
		if (self.max_beneficiaries and self.current_beneficiaries >= self.max_beneficiaries) or \
		   (self.total_budget and self.utilized_budget >= self.total_budget):
			if self.status == "Active":
				status = "Archived"
		elif self.status == "Archived":
			status = "Active"

		self.db_set({
			"current_beneficiaries": self.current_beneficiaries,
			"utilized_budget": self.utilized_budget,
			"status": status
		})
		
		return {"status": "Success", "utilized_budget": self.utilized_budget, "current_beneficiaries": self.current_beneficiaries}

	def autoname(self):
		if not self.admission_cycle:
			frappe.throw(frappe._("Admission Cycle is mandatory for naming"))
		
		# Naming Series: SS-{CYCLE}-{SCHEME_CODE}
		if not self.scheme_code:
			frappe.throw(frappe._("Scheme Code is mandatory for naming"))
			
		self.name = f"SS-{self.admission_cycle}-{self.scheme_code}"
