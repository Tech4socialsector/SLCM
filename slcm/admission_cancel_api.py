import frappe
import json
from frappe import _
from frappe.utils import flt, now, now_datetime

try:
	import razorpay
except ImportError:
	razorpay = None

@frappe.whitelist()
def process_refund(name):
	refund = frappe.get_doc("Refund Request", name)
	
	if refund.status != "Approved":
		frappe.throw(_("Refund Request must be Approved before processing."))

	# Set status to Processing while processing
	refund.db_set("status", "Processing")
	frappe.db.commit()

	# Razorpay Integration
	razorpay_settings = frappe.get_doc("Razorpay Settings")
	api_key = razorpay_settings.api_key
	api_secret = razorpay_settings.get_password("api_secret")

	if not api_key or not api_secret:
		refund.db_set("status", "Approved") # Revert status
		frappe.throw(_("Razorpay API Key or Secret is missing in Razorpay Settings."))

	if razorpay:
		try:
			client = razorpay.Client(auth=(api_key, api_secret))
			# Refund amount should be in paise (int)
			amount_in_paise = int(flt(refund.refund_amount) * 100)
			
			refund_data = {
				"amount": amount_in_paise,
				"speed": "normal",
				"notes": {
					"refund_request_name": refund.name,
					"applicant": refund.applicant or ""
				}
			}
			
			# Initiate refund via Razorpay
			response = client.payment.refund(refund.razorpay_payment_id, refund_data)
			razorpay_refund_id = response.get("id")
			gateway_response = json.dumps(response, indent=2)
			
		except razorpay.errors.BadRequestError as e:
			# If already refunded, we can consider it a success and continue
			if "already refunded" in str(e).lower():
				# Try to find existing refund ID from Razorpay if possible, 
				# or just use a placeholder to allow the system to proceed
				razorpay_refund_id = "already_refunded"
				gateway_response = json.dumps({"message": str(e)}, indent=2)
			else:
				refund.db_set("status", "Approved")
				frappe.throw(_("Razorpay Refund Failed: {0}").format(str(e)))
		except Exception as e:
			refund.db_set("status", "Approved") # Revert status
			frappe.log_error(frappe.get_traceback(), _("Razorpay Refund Error"))
			frappe.throw(_("Razorpay Refund Failed: {0}").format(str(e)))
	else:
		refund.db_set("status", "Approved") # Revert status
		frappe.throw(_("Razorpay Python library is not installed."))

	# Create Refund Transaction
	txn = frappe.new_doc("Refund Transaction")
	txn.refund_request = refund.name
	txn.payment_request = refund.payment_request
	txn.razorpay_payment_id = refund.razorpay_payment_id
	txn.razorpay_refund_id = razorpay_refund_id
	txn.refund_amount = refund.refund_amount
	txn.status = "Processed"
	txn.gateway_response = gateway_response
	txn.processed_at = now()
	txn.insert(ignore_permissions=True)

	# Update Refund Request status to Processed
	refund.db_set("status", "Processed")

	# System Rollback
	rollback_system(refund)

	return "Success"

def rollback_system(refund):
	if isinstance(refund, str):
		refund = frappe.get_doc("Refund Request", refund)

	# 1. Cancel Offer Letter
	if refund.applicant:
		# Use offer link from Refund Request if added, otherwise fetch latest
		offer_name = None
		# Try to fetch Offer Letter linked to this applicant that is active
		offers = frappe.get_all("Offer Letter", 
			filters={"applicant": refund.applicant, "offer_status": ["not in", ["Rejected", "Withdrawn"]]},
			limit=1
		)
		if offers:
			offer_name = offers[0].name
			
		if offer_name:
			frappe.db.set_value("Offer Letter", offer_name, "offer_status", "Withdrawn")
			# Add audit log or comment
			offer_doc = frappe.get_doc("Offer Letter", offer_name)
			offer_doc.add_comment("Comment", _("Offer withdrawn following Refund Request {0}").format(refund.name))

	# 2. Release Seat
	# Seat Selection Applicant is the child table in Seat Allocation
	seat_selections = frappe.get_all("Seat Selection Applicant", 
		filters={"applicant_id": refund.applicant, "selection_status": ["not in", ["Rejected", "Offer Declined"]]},
		fields=["parent", "name"]
	)
	
	for ss in seat_selections:
		frappe.db.set_value("Seat Selection Applicant", ss.name, "selection_status", "Rejected")
		# Optionally update parent totals? Usually done via parent controller if exists
		
	# 3. Update Admission Cancellation if exists
	cancellation = frappe.get_all("Admission Cancellation", 
		filters={"applicant": refund.applicant, "status": ["!=", "Completed"]},
		limit=1
	)
	if cancellation:
		frappe.db.set_value("Admission Cancellation", cancellation[0].name, "status", "Completed")

	frappe.db.commit()

@frappe.whitelist()
def submit_admission_cancellation(**kwargs):
	"""
	Portal-safe method to submit admission cancellation.
	Maps fields from the web form to Admission Cancellation DocType.
	"""
	# Pre-validation (Check if student owns this offer etc. could be added)
	
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
