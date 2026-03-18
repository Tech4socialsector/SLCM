import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
from slcm.admission.doctype.refund_request.refund_request import create_refund_request

class AdmissionCancellation(Document):
	def after_insert(self):
		create_refund_request(self)

	def validate(self):
		self.fetch_applicant_details()
		self.set_cancellation_metadata()

	def fetch_applicant_details(self):
		if self.applicant:
			# Fetch program and campus from applicant
			applicant_doc = frappe.get_doc("Applicant", self.applicant)
			self.program = applicant_doc.program
			self.campus = applicant_doc.campus
			
			# Fetch the latest active Offer Letter for this applicant
			offer_name = frappe.db.get_value("Offer Letter", 
				{"applicant": self.applicant, "offer_status": ["not in", ["Rejected", "Withdrawn"]]},
				"name", order_by="creation desc"
			)
			if offer_name:
				self.offer = offer_name
				
				# Find fee invoice through Applicant Fee Assignment
				invoice = frappe.db.get_value("Applicant Fee Assignment", 
					{"offer_letter": offer_name, "status": ["!=", "Cancelled"]}, "fee_invoice")
				
				if invoice:
					# Find the submitted fee payment linked to this invoice
					payment = frappe.get_all("Fee Payment", 
						filters={"fee_invoice": invoice, "status": "Submitted"},
						fields=["name", "amount", "reference_number"],
						limit=1
					)
					if payment:
						self.payment_request = payment[0].name
						self.amount_paid = payment[0].amount
						self.razorpay_id = payment[0].reference_number

	def set_cancellation_metadata(self):
		if self.is_new():
			self.requested_by = frappe.session.user
			self.requested_on = now_datetime()

		if self.status in ["Approved", "Completed"]:
			if not self.cancelled_by:
				self.cancelled_by = frappe.session.user
				self.cancelled_on = now_datetime()
		else:
			self.cancelled_by = None
			self.cancelled_on = None
