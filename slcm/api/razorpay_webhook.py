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
	  - refund.processed
	  - refund.failed
	  - settlement.processed  ← new: stores settlement data in FLE Payment Log
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
	if event == "refund.processed":
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
