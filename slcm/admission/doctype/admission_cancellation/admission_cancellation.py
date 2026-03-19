import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, flt
from slcm.admission.doctype.refund_request.refund_request import create_refund_request

class AdmissionCancellation(Document):
	def after_insert(self):
		refund_name = create_refund_request(self)
		if refund_name:
			self.db_set("refund_request", refund_name)

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
				
				# Try to find payment details from Applicant Fee Assignment
				afa = frappe.get_all("Applicant Fee Assignment",
					filters={"offer_letter": offer_name, "status": ["in", ["Paid", "Converted"]]},
					fields=["name", "final_payable_amount", "fee_invoice"],
					limit=1
				)
				
				if afa:
					self.amount_paid = flt(afa[0].final_payable_amount)
					invoice = afa[0].fee_invoice
					
					# Find the fee payment linked to this invoice or assignment
					payment = frappe.get_all("Fee Payment", 
						filters={"fee_invoice": invoice, "status": ["in", ["Submitted", "Draft"]]},
						fields=["name", "amount", "reference_number"],
						order_by="creation desc",
						limit=1
					)
					if payment:
						self.payment_request = payment[0].name
						if not self.amount_paid:
							self.amount_paid = flt(payment[0].amount)
						self.razorpay_id = payment[0].reference_number
					else:
						# Look for Payment Request
						pr = frappe.get_all("Payment Request",
							filters={"reference_doctype": "Offer Letter", "reference_name": offer_name, "status": "Paid"},
							fields=["name", "amount", "transaction_id"],
							limit=1
						)
						if pr:
							self.amount_paid = flt(pr[0].amount)
							self.razorpay_id = pr[0].transaction_id

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
