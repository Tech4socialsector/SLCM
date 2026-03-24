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
		Update linked Offer Letter, Student Master, Applicant, and Seat Allocation statuses.
		Releases the seat for reallocation.
		"""
		if not self.admission_cancellation:
			return

		# Ensure "Withdrawn" status exists in Applicant Status
		if not frappe.db.exists("Applicant Status", "Withdrawn"):
			frappe.get_doc({
				"doctype": "Applicant Status",
				"status": "Withdrawn"
			}).insert(ignore_permissions=True)

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
		
		# 3. Update Applicant Status to Withdrawn
		frappe.db.set_value("Applicant", self.applicant, "application_status", "Withdrawn")

		# 4. Release Seat in Seat Allocation
		# We need to find the specific row in the Seat Allocation child table
		seat_row = frappe.db.get_value("Seat Selection Applicant", {
			"applicant_id": self.applicant,
			"selection_status": ["in", ["Selected", "Offer Issued", "Offer Accepted", "Fee Paid", "Accepted"]]
		}, "name")

		if seat_row:
			# Update the status to Withdrawn
			frappe.db.set_value("Seat Selection Applicant", seat_row, "selection_status", "Withdrawn")
			
			# Find the parent Seat Allocation document to trigger waitlist promotion
			parent_allocation = frappe.db.get_value("Seat Selection Applicant", seat_row, "parent")
			if parent_allocation:
				allocation_doc = frappe.get_doc("Seat Allocation", parent_allocation)
				# Triggering save will fire the waitlist promotion logic defined in SeatAllocation.before_save/on_update
				# We set a flag to ensure the promotion logic knows this was a rejection/withdrawal
				allocation_doc.save(ignore_permissions=True)
				frappe.logger().info(f"Seat released for Applicant {self.applicant} in Allocation {parent_allocation}")

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
		elif self.applicant_payment_receipt and not self.razorpay_payment_id:
			receipt = frappe.get_doc("Applicant Payment Receipt", self.applicant_payment_receipt)
			self.amount_paid = flt(receipt.total_amount)
			self.razorpay_payment_id = receipt.transaction_id

	def apply_refund_policy(self):
		if self.refund_type == "Full":
			self.refund_amount = self.amount_paid
			return
		
		if self.refund_type == "No Refund":
			self.refund_amount = 0
			return

		# If partial, but no policy selected, try to auto-select
		amount_paid = flt(self.amount_paid)
		
		# Use shared utility to get correct policies for this applicant's Fee Structure
		from slcm.admission.utils.refund import get_applicant_refund_policies
		res = get_applicant_refund_policies(self.applicant)
		
		policies = res.get("policies", [])
		days = res.get("days_since_payment", 0)

		if not self.refund_policy:
			if not policies:
				self.refund_type = "No Refund"
				self.refund_amount = 0
				return

			for p in policies:
				if days <= p.get("days_from_payment"):
					self.refund_policy = p.get("policy_name")
					break
			if not self.refund_policy and policies:
				# Default to the most restrictive policy if over all day limits
				self.refund_policy = policies[-1].get("policy_name")

		# Calculate based on selected policy
		if self.refund_policy:
			# Find the percentage from the resolved policies list
			percentage = 0
			for p in policies:
				if p.get("policy_name") == self.refund_policy:
					percentage = flt(p.get("refund_percentage"))
					break
			
			if not percentage:
				# Fallback to direct DocType fetch if not in the Fee Structure list 
				# (e.g. if manually selected a global policy)
				percentage = flt(frappe.db.get_value("Refund Policy", self.refund_policy, "refund_percentage"))

			self.refund_amount = amount_paid * (percentage / 100.0)

	def handle_refund_type(self):
		if self.refund_type == "Full":
			self.refund_amount = self.amount_paid
		elif self.refund_type == "No Refund":
			self.refund_amount = 0

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

	def on_trash(self):
		"""
		Breaks the circular link with Admission Cancellation to allow deletion.
		"""
		if self.admission_cancellation:
			# Unset the link in the parent cancellation record
			frappe.db.set_value("Admission Cancellation", self.admission_cancellation, "refund_request", None)
			frappe.db.commit()

@frappe.whitelist()
def create_refund_request(cancellation):
	if isinstance(cancellation, str):
		cancellation = frappe.get_doc("Admission Cancellation", cancellation)
		
	if not cancellation.payment_request and not cancellation.applicant_payment_receipt:
		return None

	refund = frappe.new_doc("Refund Request")
	refund.applicant = cancellation.applicant
	refund.admission_cancellation = cancellation.name
	refund.status = "Draft"
	refund.refund_reason = cancellation.cancellation_reason
	
	if cancellation.payment_request:
		payment = frappe.get_doc("Fee Payment", cancellation.payment_request)
		refund.payment_request = cancellation.payment_request
		refund.razorpay_payment_id = payment.reference_number
		refund.amount_paid = flt(payment.amount)
		refund.refund_amount = flt(payment.amount)
	
	if cancellation.applicant_payment_receipt:
		receipt = frappe.get_doc("Applicant Payment Receipt", cancellation.applicant_payment_receipt)
		refund.applicant_payment_receipt = cancellation.applicant_payment_receipt
		if not refund.razorpay_payment_id:
			refund.razorpay_payment_id = receipt.transaction_id
		if not refund.amount_paid:
			refund.amount_paid = flt(receipt.total_amount)
			refund.refund_amount = flt(receipt.total_amount)
	
	refund.insert(ignore_permissions=True)
	return refund.name
