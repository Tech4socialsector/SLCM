# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _

class PaymentRequest(Document):
	def validate(self):
		if self.amount <= 0:
			frappe.throw(_("Amount must be greater than zero."))

	def on_submit(self):
		if not self.payment_url:
			self.get_payment_url()

	def get_payment_url(self):
		"""
		Generates the checkout URL using the payments app.
		"""
		if not self.payment_gateway:
			self.payment_gateway = frappe.db.get_value("Payment Gateway", {}, "name")
		
		if not self.payment_gateway:
			frappe.throw(_("Please configure and enable a Payment Gateway."))

		from payments.utils.utils import get_checkout_url
		
		url = get_checkout_url(
			payment_gateway=self.payment_gateway,
			amount=self.amount,
			currency=self.currency or "INR",
			reference_doctype=self.reference_doctype,
			reference_docname=self.reference_name,
			payer_email=self.email_to,
			payer_name=self.email_to # Fallback
		)
		
		self.db_set("payment_url", url)
		self.db_set("status", "Requested")
		
		return url

	def on_payment_authorized(self, status):
		"""
		Called by payments app after successful payment.
		"""
		if status in ["Authorized", "Completed"]:
			self.db_set("status", "Paid")
			
			# Update the referencing document
			if self.reference_doctype and self.reference_name:
				try:
					ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
					# According to requirement: Update status to "Payment Completed"
					if hasattr(ref_doc, "offer_status"):
						ref_doc.db_set("offer_status", "Payment Completed")
					elif hasattr(ref_doc, "status"):
						ref_doc.db_set("status", "Payment Completed")
						
					frappe.msgprint(_("Payment successful for {0}").format(self.reference_name))
				except Exception as e:
					frappe.log_error(frappe.get_traceback(), _("Payment Success Callback Error"))
