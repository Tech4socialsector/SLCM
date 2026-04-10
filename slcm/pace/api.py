import frappe
import json
from frappe import _, throw
from frappe.utils import flt, now_datetime

@frappe.whitelist()
def create_pace_razorpay_order(assignment_name):
	"""
	Creates a Razorpay order for a PACE fee assignment.
	"""
	try:
		assignment = frappe.get_doc("PACE Applicant Fee Assignment", assignment_name)
		
		if assignment.status == "Paid":
			frappe.throw(_("This fee assignment has already been paid."))
		
		if flt(assignment.final_payable_amount) <= 0:
			frappe.throw(_("The payable amount must be greater than zero."))

		# Find the matching active fee structure to get the payment gateway
		app = frappe.get_doc("PACE Application", assignment.applicant)
		nationality = (app.get("nationality") or "").strip().lower()
		nationality_type = "Indian" if nationality in ["indian", "india"] else "Foreign"

		matching = frappe.get_all(
			"PACE Fee Structure",
			filters={
				"pace_program": assignment.program,
				"nationality_type": nationality_type,
				"status": "Active"
			},
			order_by="valid_from desc",
			limit=1
		)
		if not matching:
			frappe.throw(_("No active Fee Structure found for this program and nationality."))
		
		fee_structure = frappe.get_doc("PACE Fee Structure", matching[0].name)
		gateway = fee_structure.payment_gateway
		if not gateway:
			gateway = frappe.db.get_value("Payment Gateway", {"is_default": 1}, "name") or "Razorpay"

		from payments.utils import get_payment_gateway_controller
		controller = get_payment_gateway_controller(gateway)
		if not controller:
			frappe.throw(_("Payment Gateway '{0}' not found or not configured.").format(gateway))

		payer_email = app.email_address or frappe.session.user
		if payer_email == "Administrator":
			payer_email = "admin@example.com" # Razorpay requires a valid email format

		# Check if a valid Payment Request with a Razorpay Order ID already exists
		existing_pr = frappe.db.get_value("Payment Request", {
			"reference_doctype": "PACE Applicant Fee Assignment",
			"reference_name": assignment.name,
			"status": "Requested",
			"razorpay_order_id": ["!=", ""]
		}, ["name", "razorpay_order_id"], as_dict=True)

		if existing_pr:
			order_id = existing_pr.razorpay_order_id
			# We'll just return this order ID instead of creating a new one
			# Note: In a production app, you might want to verify with Razorpay if this order is still valid/not expired.
			return {
				"order_id": order_id,
				"key_id": controller.api_key,
				"amount": flt(assignment.final_payable_amount) * 100, # Razorpay expects paise
				"currency": fee_structure.currency or "INR",
				"gateway": gateway,
				"payer_email": payer_email
			}

		payment_details = {
			"amount": flt(assignment.final_payable_amount),
			"title": _("PACE Fee Payment"),
			"description": _("Fee Payment for {0}").format(assignment.program),
			"reference_doctype": "PACE Applicant Fee Assignment",
			"reference_docname": assignment.name,
			"payer_email": payer_email,
			"payer_name": assignment.applicant_name,
			"currency": fee_structure.currency or "INR",
			"receipt": (assignment.name[:40])
		}

		order = controller.create_order(**payment_details)
		
		if not order or not order.get("id"):
			frappe.throw(_("Order creation failed. Please check gateway logs."))

		# Update/Create Payment Request
		_update_pace_payment_request(assignment, gateway, order.get("id"), "Requested", response_data=order)

		return {
			"order_id": order.get("id"),
			"key_id": controller.api_key,
			"amount": order.get("amount"),
			"currency": order.get("currency"),
			"gateway": gateway,
			"payer_email": payer_email
		}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "PACE Payment Order Creation Failed")
		raise

@frappe.whitelist()
def verify_pace_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, assignment_name):
	"""
	Verifies the Razorpay payment for a PACE fee assignment.
	"""
	try:
		assignment = frappe.get_doc("PACE Applicant Fee Assignment", assignment_name)
		
		# Get gateway from Payment Request
		pr_name = frappe.db.get_value("Payment Request", {
			"reference_doctype": "PACE Applicant Fee Assignment",
			"reference_name": assignment.name,
			"razorpay_order_id": razorpay_order_id
		}, "name")
		
		if not pr_name:
			frappe.throw(_("Payment Request not found for order {0}").format(razorpay_order_id))
		
		pr = frappe.get_doc("Payment Request", pr_name)
		gateway = pr.payment_gateway

		from payments.utils import get_payment_gateway_controller
		controller = get_payment_gateway_controller(gateway)
		
		# Verify Signature
		body = razorpay_order_id + "|" + razorpay_payment_id
		api_secret = controller.get_password("api_secret")
		
		controller.verify_signature(body, razorpay_signature, api_secret)
		
		# Success Logic
		assignment.db_set("status", "Paid")
		
		# Update Payment Request
		_update_pace_payment_request(assignment, gateway, razorpay_order_id, "Paid", razorpay_payment_id, 
			response_data={"payment_id": razorpay_payment_id, "signature": razorpay_signature})
		
		# Update PACE Application status if needed
		frappe.db.set_value("PACE Application", assignment.applicant, "status", "Admitted")

		return {"status": "success"}

	except Exception:
		frappe.log_error(frappe.get_traceback(), "PACE Payment Verification Failed")
		return {"status": "failed", "message": _("Payment verification failed.")}

def _update_pace_payment_request(assignment, gateway, transaction_id, status, payment_id=None, response_data=None):
	"""
	Internal utility to update/create Payment Request for PACE assignments.
	"""
	pr_name = frappe.db.get_value("Payment Request", {
		"reference_doctype": "PACE Applicant Fee Assignment",
		"reference_name": assignment.name,
		"status": ["!=", "Cancelled"]
	}, "name", order_by="creation desc")

	if pr_name:
		pr = frappe.get_doc("Payment Request", pr_name)
	else:
		pr = frappe.new_doc("Payment Request")
		pr.reference_doctype = "PACE Applicant Fee Assignment"
		pr.reference_name = assignment.name
		pr.amount = assignment.final_payable_amount
		pr.currency = frappe.db.get_value("PACE Application", assignment.applicant, "currency") or "INR"
		app_email = frappe.db.get_value("PACE Application", assignment.applicant, "email_address")
		pr.email_to = app_email or frappe.session.user

	# If document is already submitted, we must use db_set to avoid "Cannot Update After Submit" error
	if pr.name and pr.docstatus == 1:
		update_values = {
			"payment_gateway": gateway
		}
		if status == "Requested":
			update_values["razorpay_order_id"] = transaction_id
			update_values["status"] = "Requested"
		elif status == "Paid":
			update_values["status"] = "Paid"
			update_values["razorpay_payment_id"] = payment_id
			update_values["transaction_id"] = payment_id

		if response_data:
			update_values["gateway_response"] = json.dumps(response_data, indent=4)
		
		frappe.db.set_value("Payment Request", pr.name, update_values)
	else:
		# Document is either new or in Draft status
		pr.payment_gateway = gateway
		
		if status == "Requested":
			pr.razorpay_order_id = transaction_id
			pr.status = "Requested"
		elif status == "Paid":
			pr.status = "Paid"
			pr.razorpay_payment_id = payment_id
			pr.transaction_id = payment_id

		if response_data:
			pr.gateway_response = json.dumps(response_data, indent=4)

		if pr.name:
			pr.save(ignore_permissions=True)
		else:
			pr.insert(ignore_permissions=True)

		if status in ["Paid", "Requested"] and pr.docstatus == 0:
			pr.submit()
	
	frappe.db.commit()
