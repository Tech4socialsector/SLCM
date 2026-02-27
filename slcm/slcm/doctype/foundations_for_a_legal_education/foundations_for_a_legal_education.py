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
		if status in ["Completed", "Authorized"]:
			self.payment_status = "Paid"
			self.enrollment_status = "Enrolled"
			
			self.create_user_on_enrollment()
			self.save(ignore_permissions=True)
			
			# Read payment_id and amount from the Integration Request
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
					
					update_fields = {}
					if razorpay_payment_id:
						update_fields["payment_id"] = razorpay_payment_id
					if amount_paise:
						update_fields["paid_amount"] = flt(amount_paise) / 100.0
					
					if update_fields:
						frappe.db.set_value("Foundations for a Legal Education", self.name, update_fields)
						frappe.db.commit()
			except Exception:
				frappe.log_error(frappe.get_traceback(), "FLE: Failed to update payment_id/paid_amount from Integration Request")
			
			frappe.msgprint("Payment Authorized successfully for " + self.name)
		elif status in ["Failed", "Cancelled"]:
			valid_statuses = {"Failed": "Payment Failed", "Cancelled": "Cancelled"}
			self.payment_status = valid_statuses.get(status, "Payment Failed")
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

		# Validate that students under 18 must agree to the declaration consent
		if self.candidate_dob:
			from frappe.utils import getdate, cint
			from datetime import date
			
			dob = getdate(self.candidate_dob)
			today = date.today()
			age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
			
			if age < 18 and not cint(self.declaration_consent):
				frappe.throw("As the candidate is under 18 years of age, the declaration consent is mandatory.")

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
		if self.lms_account_created and self.generated_password_temp:
			return

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
			update_password(self.email_address, password)
			
			# Add role if exists
			if "LMS Student" in [r.name for r in frappe.get_all("Role")]:
				user.add_roles("LMS Student")
			
			self.generated_password_temp = password
			self.lms_account_created = 1
			frappe.db.commit() # Ensure user creation is committed during automated webhook
			frappe.msgprint("New LMS Student account created successfully.")
		else:
			# If user already exists, ensure they have the LMS Student role
			user = frappe.get_doc("User", self.email_address)
			if "LMS Student" not in [r.role for r in user.roles]:
				if "LMS Student" in [r.name for r in frappe.get_all("Role")]:
					user.add_roles("LMS Student")
			
			# ALWAYS generate and update the password for this specific flow if we need to send it via notification
			update_password(self.email_address, password)
			
			self.generated_password_temp = password
			self.lms_account_created = 1
			frappe.db.commit() # Ensure role update is committed
			frappe.msgprint("User already exists. Password updated and roles verified.")

