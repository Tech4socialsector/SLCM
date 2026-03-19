import frappe
import json
from frappe import _
from frappe.utils import flt, now, now_datetime

try:
	import razorpay
except ImportError:
	razorpay = None

@frappe.whitelist()
def get_refund_policies():
	"""
	Fetches active refund policies.
	"""
	return frappe.get_all("Refund Policy", 
		filters={"is_active": 1}, 
		fields=["policy_name", "days_from_payment", "refund_percentage"],
		order_by="days_from_payment asc"
	)

@frappe.whitelist()
def process_refund(name):
	refund = frappe.get_doc("Refund Request", name)
	
	if refund.status != "Approved":
		frappe.throw(_("Refund Request must be Approved before processing."))
	
	# Set status to Processing immediately
	refund.status = "Processing"
	refund.save(ignore_permissions=True)
	frappe.db.commit()
	
	if not razorpay:
		frappe.throw(_("Razorpay library is not installed."))
		
	# Razorpay Integration
	settings = frappe.get_single("Razorpay Settings")
	if not settings.api_key or not settings.api_secret:
		frappe.throw(_("Razorpay API Key or Secret not configured."))
		
	client = razorpay.Client(auth=(settings.api_key, settings.get_password("api_secret")))
	
	try:
		# Initiate refund via Razorpay API
		# Note: razorpay_payment_id should be stored in the Refund Request
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
	# Check for existing cancellation
	existing_cancellation = frappe.db.exists("Admission Cancellation", {
		"applicant": kwargs.get("applicant"),
		"offer": kwargs.get("offer")
	})
	
	if existing_cancellation:
		frappe.throw(_("A cancellation request for this offer has already been submitted."))
	
	doc = frappe.new_doc("Admission Cancellation")
	doc.applicant = kwargs.get("applicant")
	doc.offer = kwargs.get("offer")
	doc.payment_request = kwargs.get("payment_request")
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
