import datetime
import frappe
import json
import hmac
import hashlib
import requests
from frappe import _
from frappe.utils import now_datetime


@frappe.whitelist(allow_guest=True)
def handle_razorpay_webhook():
	"""
	Endpoint for Razorpay Webhooks.
	URL: https://your-site.com/api/method/slcm.api.razorpay_webhook.handle_razorpay_webhook

	Handles:
	  - payment.captured  ← NEW: marks PACE/Offer payment as Paid if client verify missed it
	  - payment.failed    ← NEW: marks PACE/Offer PR as Failed via webhook
	  - refund.processed
	  - refund.failed
	  - settlement.processed  ← stores settlement data in FLE Payment Log
	"""

	# Read raw body ONCE — frappe.request.get_data() returns empty bytes on second call
	raw_data = frappe.request.get_data()

	# 1. Verify webhook signature
	settings = frappe.get_single("Razorpay Settings")
	webhook_secret = settings.get_password("webhook_secret")

	if webhook_secret:
		razorpay_signature = frappe.get_request_header("X-Razorpay-Signature")

		if not razorpay_signature:
			frappe.throw(_("Missing Razorpay Signature Header"), frappe.PermissionError)

		secret_bytes = webhook_secret.encode("utf-8") if isinstance(webhook_secret, str) else webhook_secret

		expected_signature = hmac.new(
			secret_bytes,
			raw_data,
			hashlib.sha256
		).hexdigest()

		if not hmac.compare_digest(razorpay_signature, expected_signature):
			frappe.throw(_("Invalid Webhook Signature"), frappe.PermissionError)

	# 2. Parse JSON
	try:
		event_data = json.loads(raw_data)
	except Exception:
		frappe.logger().error("Razorpay Webhook: Invalid JSON received")
		return {"status": "error", "message": "Invalid JSON"}

	event = event_data.get("event")
	event_payload = event_data.get("payload", {})

	frappe.logger().info(f"Razorpay Webhook received: event={event}")

	# 3. Route by event type
	if event == "payment.captured":
		_handle_payment_captured_webhook(event_payload)

	elif event == "payment.failed":
		_handle_payment_failed_webhook(event_payload)

	elif event == "refund.processed":
		entity = event_payload.get("refund", {}).get("entity", {})
		handle_refund_processed(entity)

	elif event == "refund.failed":
		entity = event_payload.get("refund", {}).get("entity", {})
		handle_refund_failed(entity)

	elif event == "settlement.processed":
		entity = event_payload.get("settlement", {}).get("entity", {})
		handle_settlement_processed(entity)

	else:
		frappe.logger().info(f"Razorpay Webhook: Unhandled event type '{event}'")

	return {"status": "success"}


# ---------------------------------------------------------------------------
# Payment captured / failed handlers (PACE + Offer Letter flows)
# ---------------------------------------------------------------------------

def _resolve_pr_from_order_id(order_id):
	"""
	Look up Payment Request by razorpay_order_id (primary) then transaction_id (fallback).
	Returns (pr_name, reference_doctype, reference_name) or (None, None, None).
	"""
	if not order_id:
		return None, None, None

	pr_name = (
		frappe.db.get_value(
			"Payment Request",
			{"razorpay_order_id": order_id, "docstatus": ["!=", 2]},
			"name",
		) or
		frappe.db.get_value(
			"Payment Request",
			{"transaction_id": order_id, "docstatus": ["!=", 2]},
			"name",
		)
	)
	if not pr_name:
		return None, None, None

	ref_doctype, ref_name = frappe.db.get_value(
		"Payment Request", pr_name, ["reference_doctype", "reference_name"]
	)
	return pr_name, ref_doctype, ref_name


def _handle_payment_captured_webhook(event_payload):
	"""
	Razorpay payment.captured webhook handler for PACE and Offer Letter flows.

	This fires when payment is captured by Razorpay. If the browser tab closed before
	the client-side verify_pace_payment_signature call completed, this webhook ensures
	the payment is still recorded in our system.
	"""
	payment = event_payload.get("payment", {}).get("entity", {})
	order_id = payment.get("order_id", "")
	payment_id = payment.get("id", "")

	if not order_id or not payment_id:
		frappe.logger().warning("Razorpay Webhook: payment.captured has no order_id or payment_id")
		return

	pr_name, ref_doctype, ref_name = _resolve_pr_from_order_id(order_id)

	if not pr_name:
		frappe.logger().info(
			f"Razorpay Webhook: payment.captured — no Payment Request found for order_id={order_id}. "
			f"May be handled by slcm.slcm.api (Re Exam / Fee Invoice flow)."
		)
		return

	frappe.logger().info(
		f"Razorpay Webhook: payment.captured — PR={pr_name}, doctype={ref_doctype}, ref={ref_name}, payment_id={payment_id}"
	)

	# ── PACE Applicant Fee Assignment ────────────────────────────────────────
	if ref_doctype == "PACE Applicant Fee Assignment":
		try:
			# SELECT FOR UPDATE: acquire a row-level lock before reading status to prevent the
			# concurrent client verify_pace_payment_signature call from processing the same payment.
			frappe.db.sql(
				"SELECT name FROM `tabPACE Applicant Fee Assignment` WHERE name = %s FOR UPDATE",
				ref_name,
			)
			assignment = frappe.get_doc("PACE Applicant Fee Assignment", ref_name, check_permission=False)
			assignment.reload()  # Reload after lock to get the freshest DB state

			# Idempotency: skip if already Paid (client verify beat us to it)
			if assignment.status == "Paid":
				frappe.logger().info(f"Razorpay Webhook: PACE assignment {ref_name} already Paid — skipping.")
				return

			# Step 1: Validate payment request transaction_id belongs to the order
			pr_trans_id = frappe.db.get_value("Payment Request", pr_name, "transaction_id") or frappe.db.get_value("Payment Request", pr_name, "razorpay_order_id")
			if pr_trans_id != order_id:
				frappe.logger().error(f"Razorpay Webhook: PR mismatch for PACE assignment {ref_name}. Expected order: {pr_trans_id}, Webhook order: {order_id}")
				return

			# Step 2: Validate payload fields
			expected_amount = int(frappe.utils.flt(assignment.final_payable_amount) * 100)
			if int(payment.get("amount", 0)) != expected_amount:
				frappe.logger().error(f"Razorpay Webhook: Amount mismatch for PACE assignment {ref_name}. Expected: {expected_amount}, Webhook: {payment.get('amount')}")
				return

			if payment.get("currency") != assignment.currency:
				frappe.logger().error(f"Razorpay Webhook: Currency mismatch for PACE assignment {ref_name}. Expected: {assignment.currency}, Webhook: {payment.get('currency')}")
				return

			if payment.get("order_id") != order_id:
				frappe.logger().error(f"Razorpay Webhook: Order ID mismatch for PACE assignment {ref_name}. Expected: {order_id}, Webhook: {payment.get('order_id')}")
				return

			if payment.get("status") != "captured":
				frappe.logger().error(f"Razorpay Webhook: Status is not captured for PACE assignment {ref_name}. Status: {payment.get('status')}")
				return

			from slcm.pace.web_form.pace_application_form.pace_application_form import complete_pace_payment
			complete_pace_payment(
				assignment=assignment,
				gateway=frappe.db.get_value("Payment Request", pr_name, "payment_gateway"),
				razorpay_order_id=order_id,
				razorpay_payment_id=payment_id,
				response_data={"webhook": "payment.captured", "payment_id": payment_id, "order_id": order_id}
			)

			frappe.db.commit()
			frappe.logger().info(f"Razorpay Webhook: PACE assignment {ref_name} marked Paid via webhook.")

		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"Razorpay Webhook: PACE payment.captured handler failed — {ref_name}",
			)

	# ── Offer Letter (Applicant Admission Fee) ───────────────────────────────
	elif ref_doctype == "Offer Letter":
		try:
			# SELECT FOR UPDATE: acquire a row-level lock before reading status
			frappe.db.sql(
				"SELECT name FROM `tabOffer Letter` WHERE name = %s FOR UPDATE",
				ref_name,
			)
			offer = frappe.get_doc("Offer Letter", ref_name, check_permission=False)
			offer.reload()

			# Idempotency: skip if already Payment Completed
			if offer.offer_status == "Payment Completed":
				frappe.logger().info(f"Razorpay Webhook: Offer {ref_name} already Payment Completed — skipping.")
				return

			# Step 1: Validate payment request transaction_id belongs to the order
			pr_trans_id = frappe.db.get_value("Payment Request", pr_name, "transaction_id") or frappe.db.get_value("Payment Request", pr_name, "razorpay_order_id")
			if pr_trans_id != order_id:
				frappe.logger().error(f"Razorpay Webhook: PR mismatch for Offer {ref_name}. Expected order: {pr_trans_id}, Webhook order: {order_id}")
				return

			# Step 2: Validate payload fields
			expected_amount = int(frappe.utils.flt(offer.payable_amount) * 100)
			if int(payment.get("amount", 0)) != expected_amount:
				frappe.logger().error(f"Razorpay Webhook: Amount mismatch for Offer {ref_name}. Expected: {expected_amount}, Webhook: {payment.get('amount')}")
				return

			offer_currency = "INR"
			if payment.get("currency") != offer_currency:
				frappe.logger().error(f"Razorpay Webhook: Currency mismatch for Offer {ref_name}. Expected: {offer_currency}, Webhook: {payment.get('currency')}")
				return

			if payment.get("order_id") != order_id:
				frappe.logger().error(f"Razorpay Webhook: Order ID mismatch for Offer {ref_name}. Expected: {order_id}, Webhook: {payment.get('order_id')}")
				return

			if payment.get("status") != "captured":
				frappe.logger().error(f"Razorpay Webhook: Status is not captured for Offer {ref_name}. Status: {payment.get('status')}")
				return

			from slcm.api.service.fee_service import FeeService
			FeeService.complete_offer_payment(
				offer,
				payment_id,
				order_id,
				frappe.db.get_value("Payment Request", pr_name, "payment_gateway"),
				response_data={"webhook": "payment.captured", "payment_id": payment_id, "order_id": order_id}
			)
			frappe.db.commit()
			frappe.logger().info(f"Razorpay Webhook: Offer {ref_name} payment processed via webhook.")

		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"Razorpay Webhook: Offer payment.captured handler failed — {ref_name}",
			)

	# ── Applicant (Applicant Application Fee) ─────────────────────────────────
	elif ref_doctype == "Applicant":
		try:
			# SELECT FOR UPDATE: acquire a row-level lock before reading status
			frappe.db.sql(
				"SELECT name FROM `tabApplicant` WHERE name = %s FOR UPDATE",
				ref_name,
			)
			applicant = frappe.get_doc("Applicant", ref_name, check_permission=False)
			applicant.reload()

			# Idempotency: skip if already Paid
			if applicant.application_fee_status == "Paid":
				frappe.logger().info(f"Razorpay Webhook: Applicant {ref_name} already Paid — skipping.")
				return

			# Step 1: Validate payment request transaction_id belongs to the order
			pr_trans_id = frappe.db.get_value("Payment Request", pr_name, "transaction_id") or frappe.db.get_value("Payment Request", pr_name, "razorpay_order_id")
			if pr_trans_id != order_id:
				frappe.logger().error(f"Razorpay Webhook: PR mismatch for Applicant {ref_name}. Expected order: {pr_trans_id}, Webhook order: {order_id}")
				return

			# Step 2: Validate payload fields
			expected_amount = int(frappe.utils.flt(applicant.application_fee_amount) * 100)
			if int(payment.get("amount", 0)) != expected_amount:
				frappe.logger().error(f"Razorpay Webhook: Amount mismatch for Applicant {ref_name}. Expected: {expected_amount}, Webhook: {payment.get('amount')}")
				return

			applicant_currency = getattr(applicant, "currency", None) or frappe.defaults.get_global_default("currency") or "INR"
			if payment.get("currency") != applicant_currency:
				frappe.logger().error(f"Razorpay Webhook: Currency mismatch for Applicant {ref_name}. Expected: {applicant_currency}, Webhook: {payment.get('currency')}")
				return

			if payment.get("order_id") != order_id:
				frappe.logger().error(f"Razorpay Webhook: Order ID mismatch for Applicant {ref_name}. Expected: {order_id}, Webhook: {payment.get('order_id')}")
				return

			if payment.get("status") != "captured":
				frappe.logger().error(f"Razorpay Webhook: Status is not captured for Applicant {ref_name}. Status: {payment.get('status')}")
				return

			from slcm.api.service.fee_service import FeeService
			FeeService.complete_application_fee_payment(
				applicant,
				payment_id,
				order_id,
				frappe.db.get_value("Payment Request", pr_name, "payment_gateway"),
				response_data={"webhook": "payment.captured", "payment_id": payment_id, "order_id": order_id}
			)
			frappe.db.commit()
			frappe.logger().info(f"Razorpay Webhook: Applicant {ref_name} payment processed via webhook.")

		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"Razorpay Webhook: Applicant payment.captured handler failed — {ref_name}",
			)


def _handle_payment_failed_webhook(event_payload):
	"""
	Razorpay payment.failed webhook handler for PACE and Offer Letter flows.
	Updates Payment Request status to Failed for audit trail.
	"""
	payment = event_payload.get("payment", {}).get("entity", {})
	order_id = payment.get("order_id", "")
	payment_id = payment.get("id", "")
	error_desc = payment.get("error_description") or payment.get("error_reason") or "Payment failed at gateway"

	if not order_id:
		return

	pr_name, ref_doctype, ref_name = _resolve_pr_from_order_id(order_id)

	if not pr_name:
		return

	if ref_doctype not in ("PACE Applicant Fee Assignment", "Offer Letter", "Applicant"):
		return

	try:
		current_status = frappe.db.get_value("Payment Request", pr_name, "status")
		if current_status == "Paid":
			return  # Don't overwrite a successful payment

		frappe.db.set_value(
			"Payment Request",
			pr_name,
			{
				"status": "Failed",
				"failure_message": error_desc,
				"gateway_status": "failed",
				"gateway_response": json.dumps(payment, indent=4),
			},
			update_modified=True,
		)
		frappe.db.commit()
		frappe.logger().info(
			f"Razorpay Webhook: payment.failed — PR={pr_name} marked Failed. Order={order_id}"
		)
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			f"Razorpay Webhook: payment.failed handler failed — PR={pr_name}",
		)


# ---------------------------------------------------------------------------
# Settlement handler
# ---------------------------------------------------------------------------

def handle_settlement_processed(payload):
	"""
	When Razorpay fires settlement.processed:
	  1. Extract settlement metadata (id, utr, date, fees, tax).
	  2. Fetch per-payment recon from /v1/settlements/{id}/recon/combined.
	  3. Update FLE Payment Log records with settlement data so the
	     FLE Payment Journal report can read them without live API calls.
	"""
	settlement_id = payload.get("id")
	if not settlement_id:
		frappe.logger().warning("Razorpay Webhook: settlement.processed has no id in payload")
		return

	utr              = payload.get("utr") or ""
	settlement_status = payload.get("status") or "processed"
	created_at       = payload.get("created_at")
	settlement_date  = None
	if created_at:
		try:
			settlement_date = datetime.datetime.utcfromtimestamp(int(created_at)).date()
		except Exception:
			pass

	# Batch-level fee/tax (paise → rupees)
	batch_fees = round((payload.get("fees") or 0) / 100, 2)
	batch_tax  = round((payload.get("tax") or 0) / 100, 2)

	# Fetch credentials for recon API call
	settings   = frappe.get_single("Razorpay Settings")
	api_key    = settings.api_key
	api_secret = settings.get_password("api_secret")

	if not api_key or not api_secret:
		frappe.logger().error("Razorpay Webhook: API credentials not configured in Razorpay Settings")
		return

	# Fetch per-payment recon (paginated; max 1000 per call)
	recon_items = _fetch_settlement_recon(settlement_id, api_key, api_secret)

	updated = 0
	for item in recon_items:
		# Only process payment credits (not refund debits)
		if item.get("type") not in ("payment", None):
			continue

		rzp_payment_id = item.get("razorpay_payment_id") or item.get("entity_id") or ""
		if not rzp_payment_id:
			continue

		log_name = frappe.db.get_value(
			"FLE Payment Log",
			{"transaction_id": rzp_payment_id},
			"name"
		)
		if not log_name:
			continue

		# Per-payment recon amounts (paise → rupees)
		fee_paise    = item.get("fee") or 0
		tax_paise    = item.get("tax") or 0
		# Razorpay recon: credit = gross received, debit = refund debited
		credit_paise = item.get("credit") or item.get("amount") or 0

		frappe.db.set_value("FLE Payment Log", log_name, {
			"settlement_id":     settlement_id,
			"settlement_utr":    utr,
			"settlement_date":   settlement_date,
			"settlement_status": settlement_status,
			"gateway_fees":      round(fee_paise / 100, 2),
			"gateway_tax":       round(tax_paise / 100, 2),
			"net_settled":       round(credit_paise / 100, 2),
		})
		updated += 1

	frappe.logger().info(
		f"Razorpay settlement {settlement_id} (UTR: {utr}): updated {updated} FLE Payment Log records."
	)


def _fetch_settlement_recon(settlement_id, api_key, api_secret):
	"""Fetch all recon items for a settlement (handles pagination)."""
	items = []
	skip  = 0
	count = 500

	while True:
		url  = f"https://api.razorpay.com/v1/settlements/{settlement_id}/recon/combined"
		resp = requests.get(
			url,
			auth=(api_key, api_secret),
			params={"count": count, "skip": skip},
			timeout=30
		)
		if resp.status_code != 200:
			frappe.logger().error(
				f"Razorpay recon API error for {settlement_id}: {resp.status_code} {resp.text[:200]}"
			)
			break

		data  = resp.json()
		batch = data.get("items") or []
		items.extend(batch)

		if len(batch) < count:
			break  # last page
		skip += count

	return items


# ---------------------------------------------------------------------------
# Refund handlers (unchanged)
# ---------------------------------------------------------------------------

def handle_refund_processed(payload):
	"""
	Syncs SLCM when Razorpay confirms successful processing.
	"""
	rzp_refund_id = payload.get("id")
	if not rzp_refund_id:
		frappe.logger().warning("Razorpay Webhook: refund.processed has no refund ID in payload")
		return

	txn_name = frappe.db.get_value(
		"Refund Transaction",
		{"razorpay_refund_id": rzp_refund_id},
		"name"
	)

	if not txn_name:
		frappe.logger().warning(f"Razorpay Webhook: No Refund Transaction found for refund ID {rzp_refund_id}")
		return

	txn = frappe.get_doc("Refund Transaction", txn_name)
	txn.db_set("status", "Processed")
	if payload.get("created_at"):
		from frappe.utils import format_datetime, get_datetime
		payload["processed_date"] = format_datetime(get_datetime(payload.get("created_at")))

	txn.db_set("gateway_response", json.dumps(payload, indent=4))

	refund = frappe.get_doc("Refund Request", txn.refund_request)

	# Duplicate Safety — avoid processing twice
	if refund.status == "Processed":
		frappe.logger().info(f"Refund {refund.name} already Processed — skipping duplicate webhook.")
		return

	refund.db_set("status", "Processed")
	refund.db_set("refund_date", now_datetime())
	refund.db_set("failure_message", "")

	refund.sync_cancellation_status()

	frappe.logger().info(f"Refund {refund.name} marked as Processed via Webhook.")


def handle_refund_failed(payload):
	"""
	Handles refund failure notifications from Razorpay.
	"""
	rzp_refund_id = payload.get("id")
	if not rzp_refund_id:
		frappe.logger().warning("Razorpay Webhook: refund.failed has no refund ID in payload")
		return

	txn_name = frappe.db.get_value(
		"Refund Transaction",
		{"razorpay_refund_id": rzp_refund_id},
		"name"
	)

	if not txn_name:
		frappe.logger().warning(f"Razorpay Webhook: No Refund Transaction found for failed refund ID {rzp_refund_id}")
		return

	txn = frappe.get_doc("Refund Transaction", txn_name)
	txn.db_set("status", "Failed")
	if payload.get("created_at"):
		from frappe.utils import format_datetime, get_datetime
		payload["processed_date"] = format_datetime(get_datetime(payload.get("created_at")))

	txn.db_set("gateway_response", json.dumps(payload, indent=4))

	refund = frappe.get_doc("Refund Request", txn.refund_request)

	refund.db_set("status", "Failed")
	refund.db_set(
		"failure_message",
		payload.get("error_description", _("Refund failed at gateway."))
	)

	if refund.admission_cancellation:
		frappe.db.set_value(
			"Admission Cancellation",
			refund.admission_cancellation,
			"status",
			"Approved"
		)
	else:
		frappe.logger().warning(
			f"Refund {refund.name} has no linked admission_cancellation — skipping status revert."
		)

	frappe.logger().error(
		f"Refund {refund.name} failed via Webhook: {payload.get('error_description')}"
	)
