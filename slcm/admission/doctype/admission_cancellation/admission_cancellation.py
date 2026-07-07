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
		# Only auto-fetch on first creation to avoid overwriting manually set values
		if self.is_new():
			self.fetch_applicant_details()
		self.set_cancellation_metadata()

	def fetch_applicant_details(self):
		if not self.applicant:
			return

		# Fetch program and campus from applicant
		applicant_doc = frappe.get_doc("Applicant", self.applicant)
		self.program = applicant_doc.program
		self.campus = applicant_doc.campus

		# Fetch the latest active Offer Letter for this applicant
		offer_name = frappe.db.get_value(
			"Offer Letter",
			{"applicant": self.applicant, "status": ["not in", ["Rejected", "Withdrawn"]]},
			"name",
			order_by="creation desc"
		)
		if not offer_name:
			return

		self.offer = offer_name

		# ── Primary: resolve via Applicant Payment Receipt linked to the Offer Letter ──
		# APR.net_amount = actual amount paid (post-scholarship); APR.transaction_id = Razorpay pay_xxx
		receipt = frappe.db.get_value(
			"Applicant Payment Receipt",
			{"offer_letter": offer_name, "docstatus": ["<", 2]},
			["name", "net_amount", "total_amount", "transaction_id"],
			as_dict=True,
			order_by="creation desc"
		)

		if receipt:
			self.applicant_payment_receipt = receipt.name
			# Use net_amount (actual paid after scholarship); fallback to total_amount
			self.amount_paid = flt(receipt.net_amount) if flt(receipt.net_amount) > 0 else flt(receipt.total_amount)
			self.razorpay_id = receipt.transaction_id
			return  # APR is the authoritative source — no need to fall through

		# ── Fallback: no APR found, try Payment Request on Offer Letter ──
		pr = frappe.db.get_value(
			"Payment Request",
			{"reference_doctype": "Offer Letter", "reference_name": offer_name, "status": "Paid"},
			["name", "amount", "transaction_id"],
			as_dict=True,
			order_by="creation desc"
		)
		if pr:
			self.amount_paid = flt(pr.amount)
			self.razorpay_id = pr.transaction_id

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

	def on_trash(self):
		"""
		Breaks the circular link with Refund Request to allow deletion.
		"""
		if self.refund_request:
			# Unset the link in the child refund record
			frappe.db.set_value("Refund Request", self.refund_request, "admission_cancellation", None)
			frappe.db.commit()
