# Copyright (c) 2025, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from slcm.api.service.offer_service import OfferService

class FeeStructure(Document):
	def validate(self):
		self.validate_dates()
		self.calculate_total()

	def validate_dates(self):
		if self.valid_from and self.valid_until:
			if self.valid_from > self.valid_until:
				frappe.throw(_("Valid From date cannot be after Valid Until date"))

	def calculate_total(self):
		total = 0
		for component in self.components:
			# Calculate row level totals if missing or for consistency
			amount = component.amount or 0
			tax_rate = component.tax_rate or 0
			
			component.tax_amount = (amount * tax_rate) / 100
			component.total_amount = amount + component.tax_amount
			
			total += component.total_amount
		self.total_amount = total

	def on_update(self):
		if self.has_value_changed("valid_until") and self.valid_until:
			OfferService.extended_fee_deadline(self.name)
			frappe.msgprint(_("Fee Structure Valid Until date & Extended Fee Deadline for offer letter updated successfully."), 
				indicator="green")