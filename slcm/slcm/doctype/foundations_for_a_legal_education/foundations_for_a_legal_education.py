# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from payments.utils import get_payment_gateway_controller

class FoundationsforaLegalEducation(Document):
	def on_payment_authorized(self, status):
		"""
		This hook is called by the Frappe Payments app when a payment is successful, failed, or cancelled.
		The 'status' parameter is usually 'Completed', 'Authorized', 'Failed', etc.
		"""
		if status in ["Completed", "Authorized"]:
			self.db_set("payment_status", "Paid")
			self.db_set("enrollment_status", "Enrolled")
			
			self.create_user_on_enrollment()
			
			frappe.msgprint("Payment Authorized successfully for " + self.name)
		elif status in ["Failed", "Cancelled"]:
			valid_statuses = {"Failed": "Payment Failed", "Cancelled": "Cancelled"}
			self.db_set("payment_status", valid_statuses.get(status, "Payment Failed"))

	def before_insert(self):
		if not self.enrollment_status or self.enrollment_status == "Enrolled":
			self.enrollment_status = "In Progress"
		if not self.payment_status:
			self.payment_status = "Unpaid"

	def validate_payment(self):
		"""
		Fired from the `accept` method inside `payment_webform.py` when a user clicks the framework's native 'Proceed to Pay' button.
		"""
		self.db_set("payment_status", "Payment Initiated")

	def create_user_on_enrollment(self):
		# Check if user already exists
		if not frappe.db.exists("User", self.email_address):
			user = frappe.get_doc({
				"doctype": "User",
				"email": self.email_address,
				"first_name": self.candidate_name,
				"mobile_no": self.candidate_contact_number,
				"enabled": 1,
				"send_welcome_email": 1
			})
			user.flags.ignore_password_policy = True
			user.insert(ignore_permissions=True)
			
			if "LMS Student" in [r.role.name for r in frappe.get_all("Role")]:
				user.add_roles("LMS Student")
			
			self.db_set("lms_account_created", 1)
		else:
			frappe.msgprint("User already exists with this Email ID")

@frappe.whitelist()
def create_razorpay_order(doc_name):
	try:
		doc = frappe.get_doc("Foundations for a Legal Education", doc_name)
		
		# Ensure amount is set, default to 10000 if not
		amount = flt(doc.amount) if doc.amount else 10000.0
		
		# Use correct controller
		controller = get_payment_gateway_controller("Razorpay")
		
		# Validate API Key to prevent malformed requests and hard-to-trace frontend errors
		if not controller.api_key or not controller.api_key.startswith("rzp_") or len(controller.api_key) > 50:
			frappe.throw("Invalid Razorpay API Key configured in Razorpay Settings. Please check your credentials.")
		
		payment_details = {
			"amount": amount, # Controller converts to paise
			"title": "Application Fee",
			"description": f"Application Fee for {doc.name}",
			"reference_doctype": "Foundations for a Legal Education",
			"reference_docname": doc.name,
			"payer_email": doc.email_address,
			"payer_name": doc.candidate_name,
			"order_id": doc.name,
			"currency": "INR",
			"receipt": doc.name
		}
		
		order = controller.create_order(**payment_details)
		
		if not order or not order.get("id"):
			frappe.throw("Razorpay order creation did not return a valid order ID.")
			
		frappe.log_error("Razorpay Order Created", str(order))
		
		doc.db_set("payment_status", "Payment Initiated")
		
		return {
			"order_id": order.get("id"),
			"key_id": controller.api_key,
			"amount": order.get("amount"),
			"currency": order.get("currency")
		}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Razorpay Order Creation Failed")
		if hasattr(e, "message"):
			frappe.throw(e.message)
		else:
			frappe.throw("Failed to create payment order. Please try again or contact administrator.")

@frappe.whitelist()
def update_payment_status(doc_name, status):
	try:
		doc = frappe.get_doc("Foundations for a Legal Education", doc_name)
		valid_statuses = ["Unpaid", "Payment Initiated", "Paid", "Payment Failed", "Refunded", "Cancelled"]
		if status in valid_statuses:
			doc.db_set("payment_status", status)
		return {"status": "success"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), f"Payment Status Update to {status} Failed")
		return {"status": "failed", "message": str(e)}

@frappe.whitelist()
def verify_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, doc_name):
	try:
		controller = get_payment_gateway_controller("Razorpay")
		
		# Verify signature
		# RazorpaySettings.verify_signature(body, signature, key)
		body = razorpay_order_id + "|" + razorpay_payment_id
		api_secret = controller.get_password("api_secret")
		
		controller.verify_signature(body, razorpay_signature, api_secret)
		
		# Update Document Status
		doc = frappe.get_doc("Foundations for a Legal Education", doc_name)
		doc.db_set("payment_status", "Paid")
		doc.db_set("enrollment_status", "Enrolled")
		doc.db_set("payment_instructions", f"Payment successful. Reference ID: {razorpay_payment_id}")
		
		doc.create_user_on_enrollment()
		
		return {"status": "success"}
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Razorpay Payment Verification Failed")
		return {"status": "failed", "message": str(e)}

@frappe.whitelist(allow_guest=True)
def get_receipt_details(doc_name=None):
	try:
		if not doc_name:
			# If doc_name is not in URL, try to find the latest "Paid" record for this session/user
			filters = {"payment_status": "Paid"}
			if frappe.session.user != "Guest":
				filters["email_address"] = frappe.session.user
			
			latest_docs = frappe.get_all(
				"Foundations for a Legal Education",
				filters=filters,
				order_by="modified desc",
				limit=1
			)
			if not latest_docs:
				return None
			doc_name = latest_docs[0].name
			
		doc = frappe.get_doc("Foundations for a Legal Education", doc_name)
		return {
			"candidate_name": doc.candidate_name,
			"email_address": doc.email_address,
			"name": doc.name,
			"amount": doc.amount,
			"modified": doc.modified,
			"payment_status": doc.payment_status or "Paid"
		}
	except Exception:
		return None

# Added space for git commit as requested
