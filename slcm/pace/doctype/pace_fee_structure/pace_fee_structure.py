# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PACEFeeStructure(Document):

	def validate(self):
		self.calculate_totals()
		self.validate_dates()
		self.set_status()
		self.validate_active_fee_structure()

	def calculate_totals(self):
		total_indian = 0
		total_foreign = 0
		
		for table in ["fee_components_for_indians", "fee_components_for_foreign", "other_fees"]:
			seen_components = set()
			for row in self.get(table) or []:
				if row.fee_component in seen_components:
					frappe.throw(_("Fee Component '{0}' is duplicated in {1}").format(
						row.fee_component, table.replace("_", " ").title()
					))
				seen_components.add(row.fee_component)
				
				self.calculate_component(row)
				
				if table == "fee_components_for_indians":
					total_indian += row.total_amount
				elif table == "fee_components_for_foreign":
					total_foreign += row.total_amount
				elif table == "other_fees":
					total_indian += row.total_amount
					total_foreign += row.total_amount

		self.total_amount = total_indian
		self.total_amount_for_foreign = total_foreign

	def calculate_component(self, row):
		if row.amount < 0:
			frappe.throw(_("Amount cannot be negative for component: {0}").format(row.fee_component))

		if getattr(row, "tax_rate", 0):
			row.tax_amount = (row.amount * row.tax_rate) / 100
		else:
			row.tax_amount = 0

		row.total_amount = row.amount + row.tax_amount

	def validate_dates(self):
		from frappe.utils import getdate, nowdate
		today = getdate(nowdate())

		if self.valid_from and (self.is_new() or self.has_value_changed("valid_from")):
			if getdate(self.valid_from) < today:
				frappe.throw(_("Valid From date cannot be a past date"))

		if self.valid_from and self.valid_to:
			if getdate(self.valid_from) > getdate(self.valid_to):
				frappe.throw(_("Valid From cannot be greater than Valid Until"))

	def set_status(self):
		from frappe.utils import getdate, nowdate
		if self.valid_to and getdate(self.valid_to) < getdate(nowdate()):
			if self.status != "Inactive":
				self.status = "Inactive"

	def validate_active_fee_structure(self):
		if self.status == "Active":
			filters = {
				"pace_program": self.pace_program,
				"academic_year": self.academic_year,
				"status": "Active",
				"name": ["!=", self.name]
			}
			existing = frappe.get_all("PACE Fee Structure", filters=filters)

			if existing:
				frappe.throw(_("Only one active fee structure allowed for this program and academic year"))
