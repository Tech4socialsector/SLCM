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
		
		# Create order
		# The controller might wrap create_order or we might need to use its method directly
		# Standard Razorpay controller in Frappe (payments app) usually has create_order which returns a dict
		
		# If the controller is the `RazorpaySettings` (which get_payment_gateway_controller might return an instance of wrapper),
		# we need to be careful.
		# Actually, `get_payment_gateway_controller` returns an instance of the Gateway Controller class (e.g. Razorpay)
		
		frappe.log_error("Razorpay Payment Details", str(payment_details))
		order = controller.create_order(**payment_details)
		frappe.log_error("Razorpay Order Created", str(order))
		
		return {
			"order_id": order.get("id"),
			"key_id": controller.api_key,
			"amount": order.get("amount"),
			"currency": order.get("currency")
		}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Razorpay Order Creation Failed")
		frappe.throw("Failed to create payment order. Please try again.")

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
