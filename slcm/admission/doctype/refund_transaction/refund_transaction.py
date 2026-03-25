import frappe
from frappe.model.document import Document
from frappe.utils import flt

class RefundTransaction(Document):
	def validate(self):
		self.fetch_request_details()

	def fetch_request_details(self):
		if self.refund_request and not self.razorpay_payment_id:
			request = frappe.get_doc("Refund Request", self.refund_request)
			self.payment_request = request.payment_request
			self.razorpay_payment_id = request.razorpay_payment_id
			self.refund_amount = flt(request.refund_amount)
