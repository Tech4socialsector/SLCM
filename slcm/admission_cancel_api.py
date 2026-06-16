#SLCM
import frappe
import json
from frappe import _
from frappe.utils import flt, now, now_datetime

try:
	import razorpay
except ImportError:
	razorpay = None

def log_refund_audit_action(refund, action_type, remarks, old_value=None, new_value=None, snapshot=None):
	"""
	Logs the refund action to the Admission Audit Log.
	"""
	try:
		from frappe.utils import now_datetime
		audit = frappe.get_doc({
			"doctype": "Admission Audit Log",
			"reference_doctype": "Refund Request",
			"reference_name": refund.name,
			"action": action_type,
			"action_type": action_type,
			"applicant": refund.applicant,
			"performed_by": frappe.session.user or "System",
			"performed_on": now_datetime(),
			"timestamp": now_datetime(),
			"remarks": remarks,
			"old_value": str(old_value) if old_value is not None else "",
			"new_value": str(new_value) if new_value is not None else "",
			"snapshot_json": json.dumps(snapshot, indent=4) if snapshot else "",
			"ip_address": frappe.local.request_ip if hasattr(frappe.local, "request_ip") else "",
			"legal_relevance": "Fee"
		})
		audit.insert(ignore_permissions=True)
	except Exception as e:
		frappe.log_error(f"Failed to create refund audit log: {str(e)}", "Refund Audit Log Error")

@frappe.whitelist()
def get_refund_policies(applicant=None, program=None, campus=None, offer=None):
	"""
	Fetches refund policies mapped to the applicant's Fee Structure.
	If is_refund_available is unchecked or table is empty, returns empty list.
	"""
	from slcm.admission.utils.refund import get_applicant_refund_policies

	if not applicant:
		user_email = frappe.session.user
		applicant = frappe.db.get_value("Applicant", {"email": user_email}, "name")

	if not applicant:
		return {"policies": [], "days_since_payment": 0}

	res = get_applicant_refund_policies(applicant)
	
	return {
		"policies": res.get("policies") or [],
		"days_since_payment": res.get("days_since_payment") or 0
	}

@frappe.whitelist()
def process_refund(name):
	# ── Concurrency Protection (Redis lock) ──
	r = frappe.cache()
	lock_key = f"lock:refund_request:{name}"
	if not r.set(lock_key, "1", ex=120, nx=True):
		frappe.throw(_("Refund Request {0} is currently being processed by another task/user. Please wait.").format(name))

	try:
		# ── Concurrency Protection (Database SELECT FOR UPDATE lock) ──
		frappe.db.sql("SELECT name, status FROM `tabRefund Request` WHERE name = %s FOR UPDATE", (name,))
		
		refund = frappe.get_doc("Refund Request", name)
		refund.reload()

		if refund.status == "Processed":
			frappe.throw(_("Refund Request has already been processed successfully."))

		# Skip already processing/pending states
		if refund.status in ("Processing", "Pending Gateway Confirmation"):
			frappe.throw(_("Refund Request is already in {0} state.").format(refund.status))

		if refund.status not in ("Approved", "Queued"):
			frappe.throw(_("Refund Request must be Approved or Queued before processing."))

		if refund.refund_type == "No Refund":
			# No payment needed, just close the cycle
			refund.db_set("status", "Processed")
			refund.db_set("refund_date", now_datetime())
			refund.db_set("failure_message", "")
			
			# Create a 0-amount transaction for audit trail
			rt = frappe.new_doc("Refund Transaction")
			rt.refund_request = refund.name
			rt.payment_request = refund.payment_request
			rt.razorpay_payment_id = refund.razorpay_payment_id
			rt.razorpay_refund_id = "INTERNAL_NO_REFUND"
			rt.refund_amount = 0
			rt.status = "Processed"
			rt.processed_at = now_datetime()
			rt.gateway_response = json.dumps({"note": "Refund skipped: Processed as 'No Refund' in system."})
			rt.insert(ignore_permissions=True)
			
			# Sync statuses (closes the Admission Cancellation)
			refund.sync_cancellation_status()
			
			log_refund_audit_action(refund, "Refund Completed", "No Refund processed successfully.", old_value="Approved", new_value="Processed")
			
			return {"status": "Success", "message": _("Refund Request (No Refund) has been closed successfully.")}

		if not refund.razorpay_payment_id:
			frappe.throw(_("Cannot process refund: No Razorpay Payment ID found on this request."))

		if refund.razorpay_refund_id:
			# If ID exists but status is not Processed, try to sync it
			return update_razorpay_refund_status(name)
		
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
		
		# ── Idempotency Check / Network Failure Safety (Reconciliation against Razorpay refunds list) ──
		existing_rzp_refund = None
		try:
			# Fetch all refunds associated with the payment
			rzp_refunds_response = client.payment.fetch_multiple_refund(refund.razorpay_payment_id)
			if rzp_refunds_response and rzp_refunds_response.get("items"):
				for item in rzp_refunds_response.get("items", []):
					notes = item.get("notes") or {}
					if notes.get("refund_request") == refund.name:
						existing_rzp_refund = item
						break
		except Exception as e:
			frappe.log_error(f"Razorpay Fetch Refunds List Error before refund: {str(e)}", "Refund Process")

		if existing_rzp_refund:
			# Recover: refund was already created on Razorpay!
			rzp_id = existing_rzp_refund.get("id")
			refund.db_set("razorpay_refund_id", rzp_id)
			refund.db_set("status", "Processing")
			
			# Create/check Refund Transaction
			existing_txn = frappe.db.get_value("Refund Transaction", {"razorpay_refund_id": rzp_id}, "name")
			if not existing_txn:
				rt = frappe.new_doc("Refund Transaction")
				rt.refund_request = refund.name
				rt.payment_request = refund.payment_request
				rt.razorpay_payment_id = refund.razorpay_payment_id
				rt.razorpay_refund_id = rzp_id
				rt.refund_amount = refund.refund_amount
				rt.status = "Pending Gateway Confirmation"
				rt.processed_at = now_datetime()
				rt.gateway_response = json.dumps(existing_rzp_refund, indent=4)
				rt.insert(ignore_permissions=True)
				frappe.db.commit()

			log_refund_audit_action(refund, "Refund Recovered", f"Existing Razorpay refund {rzp_id} detected. Syncing status.", new_value="Processing", snapshot=existing_rzp_refund)
			return update_razorpay_refund_status(name)

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
				log_refund_audit_action(refund, "Refund Failed", error_msg, old_value="Processing", new_value="Failed")
				return {"status": "Error", "message": error_msg}
		except Exception as e:
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
		
		# Call Razorpay with unique Idempotency Key header (X-Refund-Idempotency is the official Razorpay Refund header)
		rzp_refund = client.payment.refund(
			refund.razorpay_payment_id, 
			refund_data, 
			headers={"X-Refund-Idempotency": refund.name}
		)
		
		if rzp_refund.get("id"):
			rzp_id = rzp_refund.get("id")
			
			# ── Transaction-Safe local database updates ──
			try:
				# Update Refund Request
				refund.razorpay_refund_id = rzp_id
				refund.status = "Processing"
				refund.failure_message = ""
				refund.save(ignore_permissions=True)
				
				# Create Refund Transaction
				rt = frappe.new_doc("Refund Transaction")
				rt.refund_request = refund.name
				rt.payment_request = refund.payment_request
				rt.razorpay_payment_id = refund.razorpay_payment_id
				rt.razorpay_refund_id = rzp_id
				rt.refund_amount = refund.refund_amount
				rt.status = "Pending Gateway Confirmation"
				rt.processed_at = now_datetime()
				
				# Add human-readable date for gateway response
				if rzp_refund.get("created_at"):
					from frappe.utils import format_datetime, get_datetime
					rzp_refund["processed_date"] = format_datetime(get_datetime(rzp_refund.get("created_at")))
					
				rt.gateway_response = json.dumps(rzp_refund, indent=4)
				rt.insert(ignore_permissions=True)
				
				# Commit transaction cleanly
				frappe.db.commit()
				
				log_refund_audit_action(refund, "Refund Initiated", f"Refund {rzp_id} created in Razorpay. Status is pending gateway confirmation.", old_value="Processing", new_value="Processing", snapshot=rzp_refund)
			except Exception as db_err:
				# Rollback transaction to avoid inconsistencies
				frappe.db.rollback()
				
				# Fallback: Save the refund ID and status in an isolated transaction to prevent losing the link
				try:
					frappe.db.set_value("Refund Request", refund.name, {
						"razorpay_refund_id": rzp_id,
						"status": "Processing",
						"failure_message": f"Local Database error after Razorpay success: {str(db_err)}"
					})
					frappe.db.commit()
				except Exception as recovery_err:
					frappe.log_error(f"Failed to save refund ID in recovery fallback: {str(recovery_err)}")
				
				frappe.log_error(f"DB transaction failed after Razorpay success: {str(db_err)}", "Refund Process DB Failure")
				raise db_err

			# Notify applicant (webhook will send notification on 'Processed', but we keep a fallback log)
			try:
				from slcm.admission.notification_service import notify_refund_processed
				notify_refund_processed(refund.name)
			except Exception as e:
				frappe.log_error(f"Refund Notification Failed: {str(e)}", "Refund Process")
			
			return {
				"status": "Success", 
				"doc_status": "Processing",
				"message": _("Refund initiated successfully. Awaiting confirmation from payment gateway.")
			}
		else:
			refund.db_set("status", "Failed")
			refund.db_set("failure_message", _("Refund failed at Razorpay."))
			log_refund_audit_action(refund, "Refund Failed", "Razorpay returned empty refund ID.", old_value="Processing", new_value="Failed")
			return {"status": "Error", "message": _("Refund failed at Razorpay.")}
			
	except Exception as e:
		if isinstance(e, frappe.ValidationError):
			raise

		# Reload to see if we recovered the ID or if status was updated
		try:
			ref_doc = frappe.db.get_value("Refund Request", name, ["status", "razorpay_refund_id"], as_dict=True)
			if ref_doc and not ref_doc.razorpay_refund_id:
				frappe.db.set_value("Refund Request", name, {
					"status": "Failed",
					"failure_message": str(e)
				})
				frappe.db.commit()
		except Exception:
			pass
			
		frappe.log_error(frappe.get_traceback(), _("Razorpay Refund Error"))
		return {"status": "Error", "message": str(e)}
	finally:
		r.delete(lock_key)

@frappe.whitelist()
def process_bulk_refunds(names):
	if isinstance(names, str):
		names = json.loads(names)
	
	if not names:
		return {"status": "NoRecords"}

	# Set status of all selected requests to "Queued" to block concurrent edits
	for name in names:
		frappe.db.set_value("Refund Request", name, "status", "Queued")
	frappe.db.commit()

	# Enqueue processing using a background job so the web request returns immediately
	frappe.enqueue(
		"slcm.admission_cancel_api.bulk_refund_worker",
		queue="long",
		timeout=1800,
		names=names,
		user=frappe.session.user,
		now=frappe.flags.in_test
	)

	return {"status": "Started", "count": len(names)}

def bulk_refund_worker(names, user=None):
	if user:
		frappe.set_user(user)

	total = len(names)
	success_count = 0
	failed_count = 0

	for i, name in enumerate(names):
		# Publish live progress to browser
		frappe.publish_realtime(
			"bulk_refund_progress",
			{
				"progress": i + 1,
				"total": total,
				"message": _("Processing refund {0} of {1}: {2}").format(i + 1, total, name),
				"doctype": "Refund Request"
			},
			user=user
		)

		try:
			process_refund(name)
			success_count += 1
		except Exception as e:
			failed_count += 1
			frappe.log_error(
				f"Bulk Refund Processing failed for {name}: {str(e)}", 
				"Bulk Refund Worker Error"
			)

	# Notify completion
	frappe.publish_realtime(
		"bulk_refund_complete",
		{
			"message": _("Bulk refund processing completed. Success: {0}, Failed: {1}").format(success_count, failed_count),
			"success_count": success_count,
			"failed_count": failed_count,
			"doctype": "Refund Request"
		},
		user=user
	)

@frappe.whitelist()
def update_razorpay_refund_status(name):
	"""
	Fetches the latest status of a refund from Razorpay API 
	and updates the Refund Request accordingly.
	"""
	refund = frappe.get_doc("Refund Request", name)
	
	if not refund.razorpay_refund_id:
		frappe.throw(_("No Razorpay Refund ID found to check status."))

	if not razorpay:
		frappe.throw(_("Razorpay library is not installed."))
		
	settings = frappe.get_single("Razorpay Settings")
	client = razorpay.Client(auth=(settings.api_key, settings.get_password("api_secret")))
	
	try:
		# Fetch status from Razorpay
		rzp_refund = client.refund.fetch(refund.razorpay_refund_id)
		rzp_status = rzp_refund.get("status") # e.g., 'processed', 'pending', 'failed'
		
		# Sync Refund Transaction doc status if it exists
		txn_name = frappe.db.get_value("Refund Transaction", {"razorpay_refund_id": refund.razorpay_refund_id}, "name")
		
		if rzp_status == "processed":
			if refund.status != "Processed":
				# Atomic Database updates
				refund.db_set("status", "Processed")
				if not refund.refund_date:
					refund.db_set("refund_date", now_datetime())
				refund.db_set("failure_message", "")
				
				if txn_name:
					frappe.db.set_value("Refund Transaction", txn_name, {
						"status": "Processed",
						"gateway_response": json.dumps(rzp_refund, indent=4)
					})
				
				refund.sync_cancellation_status()
				
				log_refund_audit_action(refund, "Refund Status Sync", "Razorpay refund verified as PROCESSED.", old_value=refund.status, new_value="Processed", snapshot=rzp_refund)
				return {"status": "Success", "message": _("Refund is officially PROCESSED at Razorpay.")}
			else:
				from frappe.utils import format_datetime
				date_str = format_datetime(refund.refund_date) if refund.refund_date else "recently"
				return {
					"status": "Success", 
					"message": _("Verified: Razorpay confirms this refund was successfully processed on {0}. (Refund ID: {1})").format(date_str, refund.razorpay_refund_id)
				}
				
		elif rzp_status == "failed":
			error_code = rzp_refund.get("error_code", "Unknown")
			error_desc = rzp_refund.get("error_description", "No description provided")
			failure_msg = f"Razorpay Failure: {error_code} - {error_desc}"
			
			if refund.status != "Failed":
				refund.db_set("status", "Failed")
				refund.db_set("failure_message", failure_msg)
				
				if txn_name:
					frappe.db.set_value("Refund Transaction", txn_name, {
						"status": "Failed",
						"failure_reason": failure_msg,
						"gateway_response": json.dumps(rzp_refund, indent=4)
					})
					
				if refund.admission_cancellation:
					frappe.db.set_value("Admission Cancellation", refund.admission_cancellation, "status", "Approved")

				log_refund_audit_action(refund, "Refund Status Sync", f"Razorpay refund FAILED: {failure_msg}", old_value=refund.status, new_value="Failed", snapshot=rzp_refund)
			return {"status": "Error", "message": _("Refund has FAILED at Razorpay: {0}").format(error_desc)}
			
		else:
			# Status like 'pending'
			if refund.status != "Processing":
				refund.db_set("status", "Processing")
				if txn_name:
					frappe.db.set_value("Refund Transaction", txn_name, "status", "Pending Gateway Confirmation")
			return {"status": "Info", "message": _("Refund status at Razorpay is: {0}").format(rzp_status.upper())}
			
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), _("Razorpay Refund Status Check Error"))
		return {"status": "Error", "message": str(e)}

@frappe.whitelist()
def reconcile_refunds():
	"""
	Reconciles and repairs out-of-sync local refunds against Razorpay gateway status.
	Runs daily via the scheduler.
	"""
	if not razorpay:
		frappe.logger().error("Reconcile Refunds: Razorpay library not installed.")
		return
		
	settings = frappe.get_single("Razorpay Settings")
	if not settings.api_key or not settings.api_secret:
		frappe.logger().error("Reconcile Refunds: Razorpay Settings not configured.")
		return

	client = razorpay.Client(auth=(settings.api_key, settings.get_password("api_secret")))
	
	# Fetch all refunds in states that need reconciliation
	refunds_to_reconcile = frappe.get_all(
		"Refund Request",
		filters={"status": ["in", ["Queued", "Processing", "Failed"]]},
		fields=["name", "status", "razorpay_payment_id", "razorpay_refund_id", "refund_type", "applicant"]
	)
	
	reconciled_count = 0
	error_count = 0
	
	for req in refunds_to_reconcile:
		name = req.name
		rzp_id = req.razorpay_refund_id
		payment_id = req.razorpay_payment_id
		
		# Skip "No Refund" requests (processed locally)
		if req.refund_type == "No Refund":
			continue

		# Concurrency lock during reconciliation to prevent race conditions
		r = frappe.cache()
		lock_key = f"lock:refund_request:{name}"
		if not r.set(lock_key, "1", ex=60, nx=True):
			continue
			
		try:
			# Check if refund ID is missing but was sent (reconstruct/detect existing)
			if not rzp_id and payment_id:
				try:
					rzp_refunds_response = client.payment.fetch_multiple_refund(payment_id)
					if rzp_refunds_response and rzp_refunds_response.get("items"):
						for item in rzp_refunds_response.get("items", []):
							notes = item.get("notes") or {}
							if notes.get("refund_request") == name:
								rzp_id = item.get("id")
								frappe.db.set_value("Refund Request", name, "razorpay_refund_id", rzp_id)
								frappe.db.commit()
								break
				except Exception as list_err:
					frappe.log_error(f"Reconciliation list refunds error for {name}: {str(list_err)}")
			
			if rzp_id:
				# Sync status with Razorpay
				res = update_razorpay_refund_status(name)
				if res.get("status") in ("Success", "Error"):
					reconciled_count += 1
			else:
				# If stuck in Processing/Queued without an ID for > 2 hours, revert to Approved (safe to retry)
				from frappe.utils import time_diff_in_seconds, now_datetime
				doc_modified = frappe.db.get_value("Refund Request", name, "modified")
				if doc_modified and time_diff_in_seconds(now_datetime(), doc_modified) > 7200:
					frappe.db.set_value("Refund Request", name, {
						"status": "Approved",
						"failure_message": _("Stuck in processing without Razorpay Refund ID. Reverted by system reconciliation.")
					})
					frappe.db.commit()
					
					refund = frappe.get_doc("Refund Request", name)
					log_refund_audit_action(refund, "Reconciliation Timeout Revert", "Stuck in processing without refund ID. Reverted to Approved.", old_value=req.status, new_value="Approved")
					reconciled_count += 1
		except Exception as err:
			error_count += 1
			frappe.log_error(f"Reconciliation failed for Refund Request {name}: {str(err)}", "Refund Reconciliation Error")
		finally:
			r.delete(lock_key)
			
	frappe.logger().info(f"Refund Reconciliation finished: {reconciled_count} reconciled, {error_count} errors.")

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
