# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from payments.utils import get_payment_gateway_controller

class FoundationsforaLegalEducation(Document):
	pass

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
		
		return {"status": "success"}
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Razorpay Payment Verification Failed")
		return {"status": "failed", "message": str(e)}

# Added space for git commit as requested
