# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

@frappe.whitelist()
def create_pace_razorpay_order(assignment_name):
    """
    Creates/Gets a Razorpay order for a PACE Applicant Fee Assignment.
    Used by both Desk (Pay Now button) and Portal.
    """
    if not assignment_name or not frappe.db.exists("PACE Applicant Fee Assignment", assignment_name):
        frappe.throw(_("Fee Assignment {0} not found.").format(assignment_name))

    assignment = frappe.get_doc("PACE Applicant Fee Assignment", assignment_name)
    if assignment.status == "Paid":
        frappe.throw(_("This fee assignment has already been paid."))

    amount = flt(assignment.final_payable_amount)
    if amount <= 0:
        frappe.throw(_("Final payable amount must be greater than zero."))
    if assignment.status == "Paid":
        return {"already_paid": True, "message": _("This fee has already been paid.")}

    # 1. Get/Create Payment Request
    pr_name = frappe.db.get_value("Payment Request", {
        "reference_doctype": "PACE Applicant Fee Assignment",
        "reference_name": assignment_name,
        "docstatus": ["!=", 2]
    })

    if pr_name:
        pr = frappe.get_doc("Payment Request", pr_name)
        if pr.status == "Paid":
             return {
                "order_id": pr.transaction_id,
                "amount": int(amount * 100),
                "currency": pr.currency,
                "key_id": frappe.db.get_value("Razorpay Settings", None, "api_key"),
                "payer_email": pr.email_to,
                "already_paid": True
            }
        
        if flt(pr.amount) != amount:
            pr.flags.ignore_permissions = True
            pr.cancel()
            pr = None
    else:
        pr = None

    # Resolve gateway from PACE Admission if possible
    academic_year = assignment.academic_year
    gateway = None
    if academic_year:
        gateway = frappe.db.get_value("PACE Admission", {"academic_year": academic_year, "status": "Active"}, "payment_gateway")
    
    if not gateway:
        gateway = frappe.db.get_value("Payment Gateway", {"is_default": 1}, "name") or "Razorpay"

    if not pr:
        pr = frappe.new_doc("Payment Request")
        pr.payment_gateway = gateway
        pr.currency = assignment.currency or "INR"
        pr.amount = amount
        pr.email_to = frappe.db.get_value("PACE Application", assignment.applicant, "email_address")
        pr.subject = _("Application Fee for {0}").format(assignment.program)
        pr.reference_doctype = "PACE Applicant Fee Assignment"
        pr.reference_name = assignment.name
        pr.flags.ignore_permissions = True
        pr.insert(ignore_permissions=True)
        pr.submit()

    # 2. Get/Create Razorpay Order
    try:
        from payments.utils import get_payment_gateway_controller
    except ImportError:
        from frappe.integrations.utils import get_payment_gateway_controller

    controller = get_payment_gateway_controller(gateway)
    
    order_id = (getattr(pr, "transaction_id", None) or getattr(pr, "razorpay_order_id", None) or "").strip()
    if not order_id:
        payment_details = {
            "amount": amount,
            "currency": pr.currency,
            "receipt": (pr.name or "PACE")[:40],
            "description": (pr.subject or "")[:255]
        }
        order = controller.create_order(**payment_details)
        order_id = (order or {}).get("id") or ""
        if order_id:
            pr.db_set({"transaction_id": order_id, "razorpay_order_id": order_id})

    settings = frappe.get_single("Razorpay Settings")
    
    return {
        "order_id": order_id,
        "amount": int(amount * 100),
        "currency": pr.currency,
        "key_id": settings.get_password("api_key") if settings.api_key else settings.api_key,
        "payer_email": pr.email_to
    }


@frappe.whitelist()
def verify_pace_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, assignment_name):
    """
    Verifies Razorpay payment and updates assignment status.
    Called as callback from Desk/Portal JS.
    """
    from slcm.pace.web_form.pace_application_form.pace_application_form import verify_pace_payment_signature
    
    # We leverage the existing verification logic in pace_application_form.py
    return verify_pace_payment_signature(
        razorpay_payment_id=razorpay_payment_id,
        razorpay_order_id=razorpay_order_id,
        razorpay_signature=razorpay_signature,
        assignment_name=assignment_name
    )


def _update_pace_payment_request(
    assignment,
    gateway,
    transaction_id,
    status,
    payment_id=None,
    response_data=None,
    failure_reason=None,
):
    """
    Internal helper to update the linked Payment Request.
    """
    import json

    pr_name = frappe.db.get_value(
        "Payment Request",
        {
            "reference_doctype": "PACE Applicant Fee Assignment",
            "reference_name": assignment.name,
            "docstatus": ["!=", 2],
        },
        "name",
        order_by="creation desc",
    )

    if not pr_name:
        return

    if frappe.db.get_value("Payment Request", pr_name, "status") == "Paid":
        return

    update_data = {"status": status}

    if status == "Paid":
        update_data["failure_message"] = None
        update_data["gateway_status"] = "captured"
        if payment_id:
            update_data["transaction_id"] = payment_id
            update_data["razorpay_payment_id"] = payment_id
    else:
        if failure_reason:
            update_data["status"] = "Failed"
            update_data["failure_message"] = failure_reason
            update_data["gateway_status"] = "failed"
        if transaction_id:
            update_data["transaction_id"] = transaction_id
            update_data["razorpay_order_id"] = transaction_id

    if gateway and frappe.db.exists("Payment Gateway", gateway):
        update_data["payment_gateway"] = gateway

    if response_data is not None:
        if isinstance(response_data, str):
            update_data["gateway_response"] = response_data
        else:
            update_data["gateway_response"] = json.dumps(response_data, indent=4)

    frappe.flags.payment_request_status_from_backend = True
    try:
        frappe.db.set_value("Payment Request", pr_name, update_data, update_modified=True)
    finally:
        if hasattr(frappe.flags, "payment_request_status_from_backend"):
            del frappe.flags.payment_request_status_from_backend


def _create_pace_receipt(assignment, transaction_id):
    """
    Internal helper to create a PACE Receipt and attach PDF.
    """
    from frappe.utils import now_datetime
    
    receipt = frappe.new_doc("PACE Receipt")
    receipt.pace_application = assignment.applicant
    receipt.fee_assignment = assignment.name
    receipt.program = assignment.program
    receipt.fee_type = assignment.fee_type
    receipt.amount = assignment.final_payable_amount
    receipt.currency = assignment.currency
    receipt.transaction_id = transaction_id
    receipt.payment_date = now_datetime()
    
    pr_name = frappe.db.get_value("Payment Request", {
        "reference_doctype": "PACE Applicant Fee Assignment",
        "reference_name": assignment.name,
        "docstatus": ["!=", 2]
    })
    if pr_name:
        receipt.payment_request = pr_name
        
    receipt.insert(ignore_permissions=True)
    
    # Generate and attach PDF if template exists
    admission_name = frappe.db.get_value("PACE Admission", {"academic_year": assignment.academic_year, "status": "Active"}, "name")
    if not admission_name:
        admission_name = _get_active_pace_admission_name()

    if admission_name:
        template = frappe.db.get_value("PACE Admission", admission_name, "payment_receipt_template")
        if template:
            from frappe.utils.pdf import get_pdf
            from frappe.utils.file_manager import save_file
            
            pdf_content = get_pdf(frappe.get_print("PACE Receipt", receipt.name, template))
            file_name = f"Receipt-{receipt.name}.pdf"
            _file = save_file(file_name, pdf_content, "PACE Receipt", receipt.name, is_private=0)
            receipt_url = _file.file_url
            receipt.db_set("receipt", receipt_url)
            receipt.receipt = receipt_url
            
    return receipt


def _get_active_pace_admission_name():
    """
    Internal helper to get the name of the currently active PACE Admission record.
    """
    return frappe.db.get_value("PACE Admission", {"status": "Active"}, "name")
