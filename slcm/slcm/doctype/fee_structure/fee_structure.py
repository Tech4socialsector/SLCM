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
		self.validate_status_transition()

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

	def validate_status_transition(self):
		"""
		Prevents setting status to 'Inactive' if it is already tied to an active Offer Configuration.
		"""
		if self.status == "Inactive" and not self.is_new():
			# Verify if it was previously active or if we're trying to set an active one to inactive
			old_status = frappe.db.get_value("Fee Structure", self.name, "status")
			if old_status != "Inactive":
				# Search child table 'Fee Structure Child' for link to this parent 'Offer Configuration'
				linked_oc = frappe.db.get_all("Fee Structure Child", 
					filters={
						"fee_structure": self.name,
						"parenttype": "Offer Configuration"
					}, 
					fields=["parent"], 
					limit=1
				)
				
				if linked_oc:
					frappe.throw(_("Cannot set status to 'Inactive'. This Fee Structure is currently used by Offer Configuration {0}. Please remove it from the configuration first.").format(linked_oc[0].parent))


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