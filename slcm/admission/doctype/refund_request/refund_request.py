import frappe
import json
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, flt

from slcm.admission.utils.withdrawal_sync import sync_student_records_for_withdrawn_application

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
			frappe.db.set_value("Offer Letter", cancellation.offer, "status", "Withdrawn")
			
		# 2. Student Master (Current Status = Withdrawn) + Student Enrollment = Dropped (if linked)
		sync_student_records_for_withdrawn_application(
			self.applicant,
			status_remark=_("Admission withdrawn and refund processed: {0}").format(self.name),
		)

		# 3. Update Applicant Status to Withdrawn
		frappe.db.set_value("Applicant", self.applicant, "status", "Withdrawn")

		# 4. Release Seat in Seat Allocation
		# We need to find the specific row in the Seat Allocation child table
		seat_row = frappe.db.get_value("Seat Selection Applicant", {
			"applicant_id": self.applicant,
			"selection_status": ["in", ["Selected", "Offer Issued", "Offer Accepted", "Confirmation Fee Paid", "Full Fee Paid", "Accepted"]]
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
		self.validate_afa_fee_type()
		self.fetch_payment_details()
		self.apply_refund_policy()
		self.handle_refund_type()
		self.validate_refund_amount()
		self.set_approval_details()
		# NOTE: process_gateway_refund() is intentionally NOT called here.
		# Gateway refunds are only triggered via the 'Process Refund' button
		# (slcm.admission_cancel_api.process_refund) which sets a Processing lock
		# before calling Razorpay, preventing duplicate API calls.


	def validate_afa_fee_type(self):
		"""Ensure only Admission Fee type AFA can be linked to a Refund Request."""
		if self.applicant_fee_assignment:
			fee_type = frappe.db.get_value(
				"Applicant Fee Assignment", self.applicant_fee_assignment, "fee_type"
			)
			if fee_type != "Admission Fee":
				frappe.throw(
					_("Only 'Admission Fee' Applicant Fee Assignments can be linked to a Refund Request. "
					  "The selected assignment is of type '{0}'.").format(fee_type or "Unknown")
				)

	def fetch_payment_details(self):
		"""Resolve payment details from Applicant Fee Assignment → Applicant Payment Receipt."""
		if self.applicant_fee_assignment and not self.razorpay_payment_id:
			# Get the latest paid Applicant Payment Receipt linked to this AFA
			receipt_name = frappe.db.get_value(
				"Applicant Payment Receipt",
				{"offer_letter": frappe.db.get_value("Applicant Fee Assignment", self.applicant_fee_assignment, "offer_letter"),
				 "docstatus": ["<", 2]},
				"name",
				order_by="creation desc"
			)
			if receipt_name:
				self.applicant_payment_receipt = receipt_name
		
		if self.applicant_payment_receipt and not self.razorpay_payment_id:
			receipt = frappe.get_doc("Applicant Payment Receipt", self.applicant_payment_receipt)
			# Use net_amount (post-scholarship) as the actual amount paid
			self.amount_paid = flt(receipt.net_amount) if flt(receipt.get('net_amount')) > 0 else flt(receipt.total_amount)
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

			# Sort policies by days_from_payment ascending to ensure correct matching
			sorted_policies = sorted(policies, key=lambda p: p.get("days_from_payment", 0))
			for p in sorted_policies:
				if days <= p.get("days_from_payment"):
					self.refund_policy = p.get("policy_name")
					break
			if not self.refund_policy and sorted_policies:
				# Exceeded all day windows — no refund applicable
				self.refund_type = "No Refund"
				self.refund_amount = 0
				return

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

		ref_field = None
		ref_value = None
		if self.applicant_payment_receipt:
			ref_field = "applicant_payment_receipt"
			ref_value = self.applicant_payment_receipt
			frappe.db.sql("SELECT name FROM `tabApplicant Payment Receipt` WHERE name = %s FOR UPDATE", ref_value)
		elif self.applicant_fee_assignment:
			ref_field = "applicant_fee_assignment"
			ref_value = self.applicant_fee_assignment
			frappe.db.sql("SELECT name FROM `tabApplicant Fee Assignment` WHERE name = %s FOR UPDATE", ref_value)

		if ref_field and ref_value:
			already_refunded = frappe.db.sql(f"""
				SELECT SUM(refund_amount) FROM `tabRefund Request`
				WHERE {ref_field} = %s AND name != %s AND status NOT IN ('Rejected', 'Failed')
				""", (ref_value, self.name))[0][0] or 0
			
			if flt(already_refunded) + flt(self.refund_amount) > flt(self.amount_paid):
				frappe.throw(_(
					"Total refund amount ({0}) would exceed the original amount paid ({1}). "
					"Already refunded/pending: {2}."
				).format(
					flt(already_refunded) + flt(self.refund_amount),
					self.amount_paid,
					already_refunded
				))

		# Allow 0 for No Refund type; otherwise enforce positive amount
		if self.refund_type != "No Refund" and flt(self.refund_amount) <= 0:
			frappe.throw(_("Refund Amount must be greater than 0"))

	def set_approval_details(self):
		if self.status == "Approved":
			if not self.approved_by:
				self.approved_by = frappe.session.user
				self.approval_date = now_datetime()
		elif self.status not in ["Processed", "Failed"]:
			self.approved_by = None
			self.approval_date = None

	def process_gateway_refund(self):
		if self.status == "Processed" and not self.razorpay_refund_id:
			if self.razorpay_payment_id and str(self.razorpay_payment_id).startswith("pay_"):
				from slcm.api.service.razorpay_utils import get_razorpay_client
				try:
					client = get_razorpay_client()
					amount_in_paise = int(flt(self.refund_amount) * 100)
					
					refund_response = client.refund.create({
						"payment_id": self.razorpay_payment_id,
						"amount": amount_in_paise,
						"notes": {
							"refund_request": self.name
						}
					}, {
						"X-Refund-Idempotency": self.name
					})
					
					if refund_response and refund_response.get("id"):
						self.razorpay_refund_id = refund_response.get("id")
						self.refund_date = now_datetime()
						self.create_refund_transaction(
							status="Processed",
							response=refund_response
						)
					else:
						frappe.throw(_("Failed to process refund at the gateway. Empty response received."))
				except Exception as e:
					frappe.log_error(frappe.get_traceback(), _("Razorpay Refund Processing Error"))
					self.create_refund_transaction(
						status="Failed",
						failure_reason=str(e)
					)
					frappe.throw(_("Gateway Refund Failed: {0}").format(str(e)))
			else:
				# Log processed cash/manual refund transaction
				self.create_refund_transaction(status="Processed")

	def create_refund_transaction(self, status, response=None, failure_reason=None):
		if not frappe.db.exists("Refund Transaction", {"refund_request": self.name, "status": status}):
			txn = frappe.get_doc({
				"doctype": "Refund Transaction",
				"refund_request": self.name,
				"applicant_fee_assignment": self.get("applicant_fee_assignment"),
				"razorpay_payment_id": self.razorpay_payment_id,
				"razorpay_refund_id": self.razorpay_refund_id or (response.get("id") if response else None),
				"refund_amount": flt(self.refund_amount),
				"status": status,
				"processed_at": now_datetime(),
				"gateway_response": json.dumps(response) if response else None,
				"failure_reason": failure_reason
			})
			txn.insert(ignore_permissions=True)

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

	# Resolve Applicant Fee Assignment for this applicant's offer
	afa_name = None
	if cancellation.offer:
		afa_name = frappe.db.get_value("Applicant Fee Assignment", {
			"applicant": cancellation.applicant,
			"offer_letter": cancellation.offer,
			"fee_type": "Admission Fee",
			"docstatus": 1
		}, "name", order_by="creation desc")

	# Resolve Payment Receipt — prefer the one already on the cancellation doc
	# (set by fetch_applicant_details), then fall back to querying via offer_letter
	receipt_name = cancellation.get("applicant_payment_receipt")

	if not receipt_name and cancellation.offer:
		receipt_name = frappe.db.get_value(
			"Applicant Payment Receipt",
			{"offer_letter": cancellation.offer, "docstatus": ["<", 2]},
			"name",
			order_by="creation desc"
		)

	# If still no receipt, try via the AFA's offer_letter (handles Converted AFA)
	if not receipt_name and afa_name:
		offer_letter = frappe.db.get_value("Applicant Fee Assignment", afa_name, "offer_letter")
		if offer_letter:
			receipt_name = frappe.db.get_value(
				"Applicant Payment Receipt",
				{"offer_letter": offer_letter, "docstatus": ["<", 2]},
				"name",
				order_by="creation desc"
			)

	# Nothing to refund if we have no payment source at all
	if not afa_name and not receipt_name and not cancellation.get("razorpay_id"):
		return None

	refund = frappe.new_doc("Refund Request")
	refund.applicant = cancellation.applicant
	refund.admission_cancellation = cancellation.name
	refund.status = "Under Review"
	refund.refund_reason = cancellation.cancellation_reason

	# Link the AFA (Admission Fee type, submitted)
	if afa_name:
		refund.applicant_fee_assignment = afa_name

	# Resolve actual paid amount & Razorpay ID from Payment Receipt
	if receipt_name:
		receipt = frappe.get_doc("Applicant Payment Receipt", receipt_name)
		refund.applicant_payment_receipt = receipt_name
		refund.razorpay_payment_id = receipt.transaction_id
		# net_amount = actual amount after scholarship deduction
		refund.amount_paid = flt(receipt.net_amount) if flt(receipt.get('net_amount')) > 0 else flt(receipt.total_amount)
		refund.refund_amount = refund.amount_paid

	# Last fallback: razorpay_id stored directly on cancellation (legacy path)
	if not refund.razorpay_payment_id and cancellation.get("razorpay_id"):
		refund.razorpay_payment_id = cancellation.razorpay_id
		refund.amount_paid = flt(cancellation.amount_paid)
		refund.refund_amount = flt(cancellation.amount_paid)

	# Safety guard: never create a refund with no amount and no payment ID
	if not refund.razorpay_payment_id and not flt(refund.amount_paid):
		frappe.log_error(
			f"Skipped Refund Request creation for Cancellation {cancellation.name}: "
			f"no Razorpay payment ID and no amount resolved.",
			"Refund Request Creation"
		)
		return None

	refund.insert(ignore_permissions=True)
	return refund.name

