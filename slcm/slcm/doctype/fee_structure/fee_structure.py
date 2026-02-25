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
		self.validate_duplicate_active_fee_structure()

	def validate_duplicate_active_fee_structure(self):
		if self.status == "Active":
			filters = {
				"program": self.program,
				"academic_year": self.academic_year,
				"academic_term": self.academic_term,
				"applicable": self.applicable,
				"offer_round": self.offer_round,
				"payment_gateway": self.payment_gateway,
				"status": "Active",
				"name": ["!=", self.name]
			}
			duplicate = frappe.db.exists("Fee Structure", filters)
			if duplicate:
				frappe.throw(_("Another active Fee Structure ({0}) already exists for the same Program, Academic Year, Academic Term, Applicable, Offer Round, and Payment Gateway.").format(duplicate))


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