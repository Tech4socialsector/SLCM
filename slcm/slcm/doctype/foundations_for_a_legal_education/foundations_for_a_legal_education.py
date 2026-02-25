# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from payments.utils import get_payment_gateway_controller

class FoundationsforaLegalEducation(Document):
	def on_payment_authorized(self, payment_status):
		"""
		Called by Frappe's payment gateway controllers (e.g. razorpay_settings) 
		when a payment is completed. Must return the exact Redirect URL.
		"""
		if payment_status in ("Authorized", "Completed", "Verified"):
			# Fetch the transaction ID from the latest Integration Request
			transaction_id = "pay_authorized"
			integration_request = frappe.get_all(
				"Integration Request",
				filters={"reference_docname": self.name, "integration_request_service": "Razorpay"},
				order_by="creation desc",
				limit=1
			)
			if integration_request:
				doc = frappe.get_doc("Integration Request", integration_request[0].name)
				import json
				data = json.loads(doc.data) if doc.data else {}
				transaction_id = data.get("razorpay_payment_id", "pay_authorized")

			# Ensure we only redirect strictly on success to skip Frappe's generic interstitial
			return f"/fle-success-page?name={self.name}&transaction_id={transaction_id}"
		return None

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
		
		# Define the precise success URL for Razorpay to redirect to upon approval
		success_url = f"/fle-success-page?name={doc.name}"
		
		return {
			"order_id": order.get("id"),
			"key_id": controller.api_key,
			"amount": order.get("amount"),
			"currency": order.get("currency"),
			"redirect_to": success_url
		}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Razorpay Order Creation Failed")
		if hasattr(e, "message"):
			frappe.throw(e.message)
		else:
			frappe.throw("Failed to create payment order. Please try again or contact administrator.")

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
		
		return {
			"status": "success",
			"receipt_id": doc_name,
			"transaction_id": razorpay_payment_id
		}
		
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
