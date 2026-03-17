# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from payments.utils import get_payment_gateway_controller

class FoundationsforaLegalEducation(Document):
	# --------------------------------------------------
	# Hook called automatically by Frappe upon handling server-to-server payment Webhooks.
	# Required to update payment status and details if the frontend callback was interrupted or missed.
	# --------------------------------------------------
	def on_payment_authorized(self, status):
		"""
		This hook is called by the Frappe Payments app when a payment is successful, failed, or cancelled.
		The 'status' parameter is usually 'Completed', 'Authorized', 'Failed', etc.
		"""
		razorpay_payment_id = None
		amount_paise = None
		paid_amount_logged = 0.0

		try:
			import json
			integration_requests = frappe.get_all(
				"Integration Request",
				filters={
					"reference_doctype": "Foundations for a Legal Education",
					"reference_docname": self.name
				},
				fields=["data"],
				order_by="modified desc",
				limit=1
			)
			if integration_requests:
				data = json.loads(integration_requests[0].get("data") or "{}")
				razorpay_payment_id = data.get("razorpay_payment_id")
				amount_paise = data.get("amount")
				if amount_paise:
					paid_amount_logged = flt(amount_paise) / 100.0
		except Exception:
			pass

		exact_status = "Pending"
		if status in ["Completed", "Authorized"]:
			# The user requested to trigger everything on "Authorized" explicitly
			exact_status = "Authorized"
		elif status == "Failed":
			exact_status = "Failed"
		elif status == "Cancelled":
			exact_status = "Cancelled"

		# Log the payment status changes
		try:
			payment_log = frappe.new_doc("FLE Payment Log")
			payment_log.reference_no = self.name
			payment_log.payment_status = exact_status
			payment_log.paid_amount = paid_amount_logged
			payment_log.transaction_id = razorpay_payment_id
			payment_log.transaction_date = frappe.utils.now_datetime()

			import json
			if integration_requests:
				# Store the raw stringified data we fetched earlier
				payment_log.gateway_response = integration_requests[0].get("data")
			
			payment_log.insert(ignore_permissions=True)
			# Do not commit just yet, as we rely on the parent transaction
		except Exception:
			frappe.log_error(frappe.get_traceback(), "FLE: Failed to create FLE Payment Log")

		if status in ["Completed", "Authorized"]:
			self.payment_status = exact_status
			self.enrollment_status = "Enrolled"
			
			self.create_user_on_enrollment()
			self.save(ignore_permissions=True)
			
			# Read payment_id and amount from the Integration Request
			try:
				update_fields = {}
				if razorpay_payment_id:
					update_fields["payment_id"] = razorpay_payment_id
				if amount_paise:
					update_fields["paid_amount"] = paid_amount_logged
				
				if update_fields:
					frappe.db.set_value("Foundations for a Legal Education", self.name, update_fields)
					frappe.db.commit()
			except Exception:
				frappe.log_error(frappe.get_traceback(), "FLE: Failed to update payment_id/paid_amount from Integration Request")
			
			frappe.msgprint("Payment Authorized successfully for " + self.name)
		elif status in ["Failed", "Cancelled"]:
			self.payment_status = exact_status
			self.save(ignore_permissions=True)


	# --------------------------------------------------
	# Fired before the document is saved. Checks for duplicate email addresses for new submissions.
	# Required to prevent multiple applications being submitted with the same email address.
	# --------------------------------------------------
	def validate(self):
		# Check for duplicate email address on new submissions
		if self.is_new():
			existing = frappe.db.exists(
				"Foundations for a Legal Education",
				{"email_address": self.email_address}
			)
			if existing:
				frappe.throw(
					f"An application with the email address '{self.email_address}' already exists (Reference: {existing}). "
					"Please use a different email address or contact support."
				)

		# Declaration consent is mandatory for all candidates
		from frappe.utils import cint
		if not cint(self.declaration_consent):
			frappe.throw("Please accept the Declaration Consent before submitting the application.")


	# --------------------------------------------------
	# Fired right before the new document is inserted into the database.
	# Required to set default statuses like "In Progress" and "Unpaid".
	# --------------------------------------------------
	def before_insert(self):
		if not self.enrollment_status or self.enrollment_status == "Enrolled":
			self.enrollment_status = "In Progress"
		if not self.payment_status:
			self.payment_status = "Unpaid"

	# --------------------------------------------------
	# Fired when a user clicks the framework's native 'Proceed to Pay' button.
	# Required to update the status to "Payment Initiated" before redirecting to gateway.
	# --------------------------------------------------
	def validate_payment(self):
		"""
		Fired from the `accept` method inside `payment_webform.py` when a user clicks the framework's native 'Proceed to Pay' button.
		"""
		self.db_set("payment_status", "Payment Initiated")

	# --------------------------------------------------
	# Generates a random password and creates a standard ERPNext User account with 'LMS Student' role for the candidate.
	# Required to grant the student system access automatically upon successful enrollment.
	# --------------------------------------------------
	def create_user_on_enrollment(self):
		from frappe.utils import random_string
		from frappe.utils.password import update_password
		
		# Ensure we only try to create exactly once
		# if self.lms_account_created and self.generated_password_temp:
		# 	return

		password = random_string(12)

		# Check if user already exists
		if not frappe.db.exists("User", self.email_address):
			user = frappe.get_doc({
				"doctype": "User",
				"email": self.email_address,
				"first_name": self.candidate_name,
				"mobile_no": self.candidate_contact_number,
				"enabled": 1,
				"send_welcome_email": 0
			})
			user.flags.ignore_password_policy = True
			user.flags.no_welcome_mail = True
			user.insert(ignore_permissions=True)
			
			# Set the password
			
			# Add role if exists
			if "LMS Student" in [r.name for r in frappe.get_all("Role")]:
				user.add_roles("LMS Student")
			
			# self.generated_password_temp = password
			self.lms_account_created = 1
			frappe.db.commit() # Ensure user creation is committed during automated webhook
			frappe.msgprint("New LMS Student account created successfully.")
		else:
			# If user already exists, ensure they have the LMS Student role
			user = frappe.get_doc("User", self.email_address)
			if "LMS Student" not in [r.role for r in user.roles]:
				if "LMS Student" in [r.name for r in frappe.get_all("Role")]:
					user.add_roles("LMS Student")
			
			# Do NOT reset the password for existing users — they registered via the FLE
			# login flow and already have a password they set themselves.
			# update_password(self.email_address, password)  # commented out: was resetting password on every payment
			
			# self.generated_password_temp = password
			self.lms_account_created = 1
			frappe.db.commit() # Ensure role update is committed
			frappe.msgprint("User already exists. Roles verified.")

