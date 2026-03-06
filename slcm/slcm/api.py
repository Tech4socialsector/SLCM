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

@frappe.whitelist(allow_guest=True)
def fle_sign_up(email: str, mobile_no: str) -> tuple[int, str]:
    if not email or not mobile_no:
        frappe.throw("Email and Mobile Number are required")
        
    user = frappe.db.get("User", {"email": email})
    if user:
        if user.enabled:
            return 0, "Already Registered"
        else:
            return 0, "Registered but disabled"
    
    from frappe.utils import random_string, escape_html
    
    # Use the first part of the email as the first name
    first_name = email.split('@')[0]
    
    user_doc = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": escape_html(first_name),
        "mobile_no": escape_html(mobile_no),
        "enabled": 1,
        "new_password": random_string(10),
        "user_type": "Website User",
        "send_welcome_email": 1
    })
    
    user_doc.flags.ignore_permissions = True
    user_doc.flags.ignore_password_policy = True
    user_doc.insert()
    
    # Set default signup role as per Portal Settings
    default_role = frappe.get_single_value("Portal Settings", "default_role")
    if default_role:
        user_doc.add_roles(default_role)
        
    if user_doc.flags.email_sent:
        return 1, "Please check your email to verify your account and set a password"
    else:
        return 1, "Registration successful. Please check your email for verification"

