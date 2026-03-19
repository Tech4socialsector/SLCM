import frappe
import json
import hmac
import hashlib
from frappe import _
from frappe.utils import now_datetime


@frappe.whitelist(allow_guest=True)
def handle_razorpay_webhook():
    """
    Endpoint for Razorpay Webhooks.
    URL: https://your-site.com/api/method/slcm.api.razorpay_webhook.handle_razorpay_webhook
    """

    # ── BUG FIX 1: Read raw data ONCE and reuse ──
    # frappe.request.get_data() returns empty bytes on second call
    raw_data = frappe.request.get_data()

    # 1. Verification of Webhook Secret (Security)
    settings = frappe.get_single("Razorpay Settings")
    webhook_secret = settings.get_password("webhook_secret")

    if webhook_secret:
        razorpay_signature = frappe.get_request_header("X-Razorpay-Signature")

        # ── BUG FIX 2: Check signature header exists before comparing ──
        if not razorpay_signature:
            frappe.throw(_("Missing Razorpay Signature Header"), frappe.PermissionError)

        # ── BUG FIX 3: webhook_secret.encode() is safe only if it's a string ──
        if isinstance(webhook_secret, str):
            secret_bytes = webhook_secret.encode("utf-8")
        else:
            secret_bytes = webhook_secret

        expected_signature = hmac.new(
            secret_bytes,
            raw_data,           # ← using saved raw_data, not calling get_data() again
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(razorpay_signature, expected_signature):
            frappe.throw(_("Invalid Webhook Signature"), frappe.PermissionError)

    # 2. Parse the Event Data
    # ── BUG FIX 1 (continued): parse from saved raw_data ──
    try:
        event_data = json.loads(raw_data)
    except Exception:
        frappe.logger().error("Razorpay Webhook: Invalid JSON received")
        return {"status": "error", "message": "Invalid JSON"}

    event = event_data.get("event")

    # ── BUG FIX 4: payload entity key may not always be 'refund' ──
    # Safely extract with fallback to empty dict
    payload = (
        event_data
        .get("payload", {})
        .get("refund", {})
        .get("entity", {})
    )

    frappe.logger().info(f"Razorpay Webhook received: event={event}")

    # 3. Route Events
    if event == "refund.processed":
        handle_refund_processed(payload)
    elif event == "refund.failed":
        handle_refund_failed(payload)
    else:
        frappe.logger().info(f"Razorpay Webhook: Unhandled event type '{event}'")

    return {"status": "success"}


def handle_refund_processed(payload):
    """
    Syncs SLCM when Razorpay confirms successful processing.
    """
    rzp_refund_id = payload.get("id")
    if not rzp_refund_id:
        frappe.logger().warning("Razorpay Webhook: refund.processed has no refund ID in payload")
        return

    # Find via Refund Transaction
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
    txn.db_set("gateway_response", json.dumps(payload, indent=4))

    refund = frappe.get_doc("Refund Request", txn.refund_request)

    # Duplicate Safety — avoid processing twice
    if refund.status == "Processed":
        frappe.logger().info(f"Refund {refund.name} already Processed — skipping duplicate webhook.")
        return

    # Update Refund Request
    refund.db_set("status", "Processed")
    refund.db_set("refund_date", now_datetime())
    refund.db_set("failure_message", "")

    # Sync with Admission Cancellation, Offer Letter, and Student Master
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
    txn.db_set("gateway_response", json.dumps(payload, indent=4))

    refund = frappe.get_doc("Refund Request", txn.refund_request)

    # Update Refund Request to Failed
    refund.db_set("status", "Failed")
    refund.db_set(
        "failure_message",
        payload.get("error_description", _("Refund failed at gateway."))
    )

    # ── BUG FIX 5: Use refund.admission_cancellation consistently ──
    # Revert Admission Cancellation back to Approved so staff can retry
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
