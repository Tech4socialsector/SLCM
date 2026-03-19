import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, flt

class RefundRequest(Document):
	def on_update(self):
		if self.admission_cancellation:
			self.sync_cancellation_status()

	def sync_cancellation_status(self):
		# Map Refund Request status to Admission Cancellation status
		status_map = {
			"Approved": "Approved",
			"Processing": "Approved",
			"Processed": "Completed"
		}
		
		new_status = status_map.get(self.status)
		if new_status:
			frappe.db.set_value("Admission Cancellation", self.admission_cancellation, "status", new_status)
		
		if self.status == "Processed":
			self.sync_linked_docs()

	def sync_linked_docs(self):
		"""
		Update linked Offer Letter and Student Master statuses after successful refund.
		"""
		if not self.admission_cancellation:
			return

		# Fetch Admission Cancellation details
		cancellation = frappe.get_doc("Admission Cancellation", self.admission_cancellation)
		
		# 1. Update Offer Letter Status to Withdrawn
		if cancellation.offer:
			frappe.db.set_value("Offer Letter", cancellation.offer, "offer_status", "Withdrawn")
			
		# 2. Update Student Master Status (if linked)
		student_name = frappe.db.get_value("Student Master", {"application_number": self.applicant}, "name")
		if student_name:
			frappe.db.set_value("Student Master", student_name, {
				"academic_status": "Inactive",
				"student_status": "Dormant",
				"status_remark": _("Admission withdrawn and refund processed: {0}").format(self.name)
			})
		
		# 3. Update Applicant Status
		frappe.db.set_value("Applicant", self.applicant, "application_status", "Cancelled")

	def validate(self):
		self.fetch_payment_details()
		self.apply_refund_policy()
		self.handle_refund_type()
		self.validate_refund_amount()
		self.set_approval_details()

	def fetch_payment_details(self):
		if self.payment_request and not self.razorpay_payment_id:
			payment = frappe.get_doc("Fee Payment", self.payment_request)
			self.amount_paid = flt(payment.amount)
			self.razorpay_payment_id = payment.reference_number

	def apply_refund_policy(self):
		if self.refund_type == "Full":
			self.refund_amount = self.amount_paid
			return

		# If partial, but no policy selected, try to auto-select
		if not self.refund_policy and self.payment_request:
			payment = frappe.get_doc("Fee Payment", self.payment_request)
			if payment.payment_date:
				from frappe.utils import date_diff, nowdate
				request_date = self.request_date or nowdate()
				days = date_diff(request_date, payment.payment_date)
				
				policies = frappe.get_all("Refund Policy", 
					filters={"is_active": 1},
					fields=["name", "refund_percentage", "days_from_payment"],
					order_by="days_from_payment asc"
				)
				
				for p in policies:
					if days <= p.days_from_payment:
						self.refund_policy = p.name
						break
				if not self.refund_policy and policies:
					self.refund_policy = policies[-1].name

		# Calculate based on selected policy
		if self.refund_policy:
			policy = frappe.get_doc("Refund Policy", self.refund_policy)
			self.refund_amount = flt(self.amount_paid) * (flt(policy.refund_percentage) / 100.0)

	def handle_refund_type(self):
		if self.refund_type == "Full":
			self.refund_amount = self.amount_paid

	def validate_refund_amount(self):
		if flt(self.refund_amount) > flt(self.amount_paid):
			frappe.throw(_("Refund Amount cannot be greater than Amount Paid ({0})").format(self.amount_paid))
		if flt(self.refund_amount) <= 0:
			frappe.throw(_("Refund Amount must be greater than 0"))

	def set_approval_details(self):
		if self.status == "Approved":
			if not self.approved_by:
				self.approved_by = frappe.session.user
				self.approval_date = now_datetime()
		elif self.status not in ["Processed", "Failed"]:
			self.approved_by = None
			self.approval_date = None

@frappe.whitelist()
def create_refund_request(cancellation):
	if isinstance(cancellation, str):
		cancellation = frappe.get_doc("Admission Cancellation", cancellation)
		
	if not cancellation.payment_request:
		return None

	payment = frappe.get_doc("Fee Payment", cancellation.payment_request)

	refund = frappe.new_doc("Refund Request")
	refund.applicant = cancellation.applicant
	refund.payment_request = cancellation.payment_request
	refund.admission_cancellation = cancellation.name
	refund.razorpay_payment_id = payment.reference_number
	refund.amount_paid = flt(payment.amount)
	refund.refund_amount = flt(payment.amount)
	refund.status = "Draft"
	refund.refund_reason = cancellation.cancellation_reason
	
	refund.insert(ignore_permissions=True)
	return refund.name
