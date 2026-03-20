import frappe
import json
from frappe import _
from frappe.utils import flt, now, now_datetime

try:
	import razorpay
except ImportError:
	razorpay = None

@frappe.whitelist()
def get_refund_policies(applicant=None, program=None, campus=None, offer=None):
	"""
	Fetches refund policies mapped to the applicant's Fee Structure.
	If is_refund_available is unchecked or table is empty, returns empty list.
	"""
	if not applicant:
		user_email = frappe.session.user
		applicant = frappe.db.get_value("Applicant", {"email": user_email}, "name")
	
	if not applicant:
		return {"policies": [], "days_since_payment": 0}

	# 1. Resolve basic details
	details = frappe.db.get_value("Applicant", applicant, ["program", "campus", "admission_cycle"], as_dict=1)
	if not details:
		return {"policies": [], "days_since_payment": 0}
	
	program = program or details.program
	campus = campus or details.campus
	cycle = details.admission_cycle

	# 2. Find Fee Structure via Offer Configuration
	fee_structure = None
	config_names = frappe.get_all("Offer Configuration", 
		filters={"admission_cycle": cycle, "campus": campus, "is_active": 1},
		pluck="name"
	)

	for cn in config_names:
		config_doc = frappe.get_doc("Offer Configuration", cn)
		for row in config_doc.fee_structure:
			fs_program = frappe.db.get_value("Fee Structure", row.fee_structure, "program")
			if fs_program == program:
				fee_structure = row.fee_structure
				break
		if fee_structure:
			break
	
	if not fee_structure:
		return {"policies": [], "days_since_payment": 0}

	# 3. Get policies from Fee Structure
	fs_doc = frappe.get_doc("Fee Structure", fee_structure)
	
	if not fs_doc.is_refund_available:
		return {"policies": [], "days_since_payment": 0}

	policies = []
	for row in fs_doc.get("refund_policies", []):
		if row.is_active:
			policies.append({
				"policy_name": row.refund_policy,
				"days_from_payment": row.days_from_payment,
				"refund_percentage": row.refund_percentage
			})
	
	# 4. Calculate days since payment
	from frappe.utils import date_diff, nowdate
	days_since_payment = 0
	last_payment = frappe.db.get_value("Applicant Payment Receipt", 
		{"applicant": applicant, "docstatus": 1}, 
		"payment_date", order_by="payment_date desc")
	
	if last_payment:
		days_since_payment = date_diff(nowdate(), last_payment)

	return {
		"policies": policies,
		"days_since_payment": days_since_payment
	}

@frappe.whitelist()
def process_refund(name):
	refund = frappe.get_doc("Refund Request", name)
	
	if refund.status == "Processed":
		frappe.throw(_("Refund Request has already been processed."))

	if refund.status != "Approved":
		frappe.throw(_("Refund Request must be Approved before processing."))
	
	# Set status to Processing immediately to prevent concurrent calls
	refund.db_set("status", "Processing")
	frappe.db.commit()
	
	if not razorpay:
		refund.db_set("status", "Failed")
		frappe.throw(_("Razorpay library is not installed."))
		
	# Razorpay Integration
	settings = frappe.get_single("Razorpay Settings")
	if not settings.api_key or not settings.api_secret:
		refund.db_set("status", "Failed")
		frappe.throw(_("Razorpay API Key or Secret not configured."))
		
	client = razorpay.Client(auth=(settings.api_key, settings.get_password("api_secret")))
	
	try:
		# Double-check if already refunded in Razorpay to prevent "Already refunded" errors
		try:
			rzp_payment = client.payment.fetch(refund.razorpay_payment_id)
			amount_to_refund_paise = int(flt(refund.refund_amount) * 100)
			
			available_paise = int(rzp_payment.get("amount", 0)) - int(rzp_payment.get("amount_refunded", 0))
			
			if available_paise < amount_to_refund_paise:
				error_msg = _("Insufficient balance in Razorpay payment. Available: {0}, Requested: {1}").format(
					available_paise / 100.0, refund.refund_amount
				)
				refund.db_set("status", "Failed")
				refund.db_set("failure_message", error_msg)
				return {"status": "Error", "message": error_msg}
		except Exception as e:
			# If fetch fails, we proceed but log it.
			frappe.log_error(f"Razorpay Fetch Error before refund: {str(e)}", "Refund Process")

		# Initiate refund via Razorpay API
		refund_data = {
			"amount": int(refund.refund_amount * 100), # Amount in paise
			"speed": "normal",
			"notes": {
				"refund_request": refund.name,
				"applicant": refund.applicant
			}
		}
		
		rzp_refund = client.payment.refund(refund.razorpay_payment_id, refund_data)
		
		if rzp_refund.get("id"):
			refund.db_set("razorpay_refund_id", rzp_refund.get("id"))
			refund.db_set("status", "Processed")
			refund.db_set("refund_date", now_datetime())
			refund.db_set("failure_message", "")
			
			# Create Refund Transaction
			rt = frappe.new_doc("Refund Transaction")
			rt.refund_request = refund.name
			rt.payment_request = refund.payment_request
			rt.razorpay_payment_id = refund.razorpay_payment_id
			rt.razorpay_refund_id = rzp_refund.get("id")
			rt.refund_amount = refund.refund_amount
			rt.status = "Processed"
			rt.processed_at = now_datetime()
			rt.gateway_response = json.dumps(rzp_refund, indent=4)
			rt.insert(ignore_permissions=True)
			
			# Trigger sync
			refund.sync_cancellation_status()
			
			return {"status": "Success", "message": _("Refund processed successfully.")}
		else:
			refund.db_set("status", "Failed")
			refund.db_set("failure_message", _("Refund failed at Razorpay."))
			frappe.msgprint(_("Refund failed at Razorpay."))
			return {"status": "Error", "message": _("Refund failed at Razorpay.")}
			
	except Exception as e:
		refund.db_set("status", "Failed")
		refund.db_set("failure_message", str(e))
		frappe.log_error(frappe.get_traceback(), _("Razorpay Refund Error"))
		frappe.msgprint(_("Razorpay Error: {0}").format(str(e)))
		return {"status": "Error", "message": str(e)}

@frappe.whitelist()
def submit_admission_cancellation(**kwargs):
	"""
	Portal-safe method to submit admission cancellation.
	Maps fields from the web form to Admission Cancellation DocType.
	"""
	applicant = kwargs.get("applicant")
	offer = kwargs.get("offer")

	# Clean up 'None' passed from template/JS
	if offer in ("None", "", None):
		offer = frappe.db.get_value("Offer Letter", 
			{"applicant": applicant, "offer_status": ["not in", ["Rejected", "Withdrawn", "Expired"]]}, 
			"name", order_by="creation desc")
	
	if not offer:
		frappe.throw(_("Could not find an active Offer Letter associated with your application."))

	# Check for existing cancellation
	existing_cancellation = frappe.db.exists("Admission Cancellation", {
		"applicant": applicant,
		"offer": offer
	})
	
	if existing_cancellation:
		frappe.throw(_("A cancellation request for this offer has already been submitted."))
	
	doc = frappe.new_doc("Admission Cancellation")
	doc.applicant = applicant
	doc.offer = offer
	
	pay_ref = kwargs.get("payment_request")
	if pay_ref:
		if frappe.db.exists("Fee Payment", pay_ref):
			doc.payment_request = pay_ref
		elif frappe.db.exists("Applicant Payment Receipt", pay_ref):
			doc.applicant_payment_receipt = pay_ref

	doc.campus = kwargs.get("campus")
	doc.program = kwargs.get("program")
	doc.cancellation_reason_type = kwargs.get("cancellation_reason_type")
	doc.cancellation_reason = kwargs.get("cancellation_reason")
	doc.additional_comments = kwargs.get("additional_comments")
	doc.cancellation_type = "Student"
	doc.status = "Initiated"
	doc.requested_by = frappe.session.user
	doc.requested_on = now_datetime()
	
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	
	return {"status": "Success", "name": doc.name}
