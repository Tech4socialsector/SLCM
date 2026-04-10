# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PACEFeeStructure(Document):
	def autoname(self):
		from frappe.model.naming import make_autoname
		self.name = make_autoname(f"{self.fee_structure_name}-{self.nationality_type}-.###")

	def validate(self):
		self.calculate_totals()
		self.validate_dates()
		self.validate_active_fee_structure()

	def calculate_totals(self):
		total = 0
		for row in self.get("fee_components"):
			self.calculate_component(row)
			total += row.total_amount

		self.total_amount = total

	def calculate_component(self, row):
		if row.amount < 0:
			frappe.throw(_("Amount cannot be negative for component: {0}").format(row.fee_component))

		if getattr(row, "tax_rate", 0):
			row.tax_amount = (row.amount * row.tax_rate) / 100
		else:
			row.tax_amount = 0

		row.total_amount = row.amount + row.tax_amount

	def validate_dates(self):
		if self.valid_from and self.valid_to:
			if self.valid_from > self.valid_to:
				frappe.throw(_("Valid From cannot be greater than Valid Until"))

	def validate_active_fee_structure(self):
		if self.status == "Active":
			filters = {
				"pace_program": self.pace_program,
				"nationality_type": self.nationality_type,
				"status": "Active",
				"name": ["!=", self.name]
			}
			existing = frappe.get_all("PACE Fee Structure", filters=filters)

			if existing:
				frappe.throw("Only one active fee structure allowed for this program and nationality type")
