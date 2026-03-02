import frappe
import json
from frappe.utils import now_datetime

@frappe.whitelist(allow_guest=True)
def razorpay_webhook():
    data = frappe.request.data
    payload = json.loads(data)

    event = payload.get("event")

    if event == "payment.captured":
        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        
        # Payment details
        notes = payment.get("notes", {})
        reference_doctype = notes.get("reference_doctype", "Foundations for a Legal Education")
        reference_name = notes.get("reference_name")

        doc = frappe.get_doc({
            "doctype": "Razorpay Payment Log",
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "razorpay_order_id": payment.get("order_id"),
            "razorpay_payment_id": payment.get("id"),
            "razorpay_signature": frappe.request.headers.get("X-Razorpay-Signature"),
            "transaction_id": payment.get("acquirer_data", {}).get("rrn"),
            "upi_id": payment.get("vpa"),
            "payment_method": payment.get("method"),
            "payment_status": payment.get("status"),
            "amount": payment.get("amount", 0) / 100 if payment.get("amount") else 0,
            "currency": payment.get("currency"),
            "payment_datetime": now_datetime(),
            "raw_response": json.dumps(payment, indent=4)
        })

        doc.insert(ignore_permissions=True)

        # Update main document
        if doc.reference_name:
            try:
                main_doc = frappe.get_doc(reference_doctype, doc.reference_name)
                
                # Update payment status based on standard FLE options
                if hasattr(main_doc, "payment_status"):
                    # Standard Select options from FLE: "Unpaid", "Payment Initiated", "Paid", "Payment Failed", "Refunded", "Cancelled"
                    main_doc.payment_status = "Paid"
                    
                main_doc.save(ignore_permissions=True)
            except frappe.DoesNotExistError:
                pass

    return "OK"
