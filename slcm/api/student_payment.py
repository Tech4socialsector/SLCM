"""
Student Portal – Secure Fee Payment API
========================================
All endpoints validate that the logged-in user owns the requested
Fee Invoice before any payment action is performed.

Security model
--------------
* Guest access → HTTP 403 on every endpoint.
* Invoice ownership: the invoice's `student` field must match the student
  record linked to `frappe.session.user`.
* Amount is always sourced from the server-side `outstanding_amount`; the
  client cannot influence the charge amount.
* CSRF: handled automatically by Frappe's @frappe.whitelist() decorator
  (requires X-Frappe-CSRF-Token header on non-GET calls).
* Razorpay signature verification is delegated to the payments app's
  `order_payment_success` handler, which performs HMAC-SHA256 validation.
"""

import hashlib
import hmac as _hmac
import json as _json

import frappe
from frappe import _
from frappe.utils import flt, today, getdate, add_days

# ── Internal helpers ───────────────────────────────────────────────────────

def _require_student():
    """Return the Student Master name for the current session user.
    Raises AuthenticationError if the user is a guest or has no student record.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to continue."), frappe.AuthenticationError)

    user = frappe.session.user
    for field in ("user", "email", "official_email_id"):
        name = frappe.db.get_value("Student Master", {field: user}, "name")
        if name:
            return name

    frappe.throw(_("No student record found for your account."), frappe.PermissionError)


def _get_owned_invoice(invoice_name, student_name):
    """Fetch a Fee Invoice that belongs to *student_name*.
    Raises PermissionError if the invoice does not exist or is owned by
    a different student (prevents IDOR).
    """
    inv = frappe.db.get_value(
        "Fee Invoice",
        {"name": invoice_name, "student": student_name},
        [
            "name", "student", "student_name",
            "outstanding_amount", "final_payable_amount",
            "paid_amount", "status",
        ],
        as_dict=True,
    )
    if not inv:
        frappe.throw(
            _("Invoice not found or you do not have permission to access it."),
            frappe.PermissionError,
        )
    return inv


def _get_razorpay_controller():
    """Return the configured Razorpay gateway controller or throw a clear error."""
    try:
        from payments.utils import get_payment_gateway_controller
        return get_payment_gateway_controller("Razorpay")
    except Exception:
        frappe.throw(
            _("Payment gateway is not configured. Please contact the Bursar's Office."),
            frappe.ValidationError,
        )


def _build_order_payload(controller, inv, student_name):
    """Create a Razorpay order for *inv* and return the full response dict."""
    sm = frappe.db.get_value(
        "Student Master",
        student_name,
        ["first_name", "last_name", "email", "official_email_id", "phone"],
        as_dict=True,
    ) or {}
    payer_name  = " ".join(filter(None, [sm.get("first_name"), sm.get("last_name")])) or inv.student_name
    payer_email = sm.get("official_email_id") or sm.get("email") or frappe.session.user
    payer_phone = sm.get("phone") or ""

    outstanding = flt(inv.outstanding_amount)

    try:
        order = controller.create_order(
            amount=outstanding,
            currency="INR",
            title=_("Fee Payment – {0}").format(inv.name),
            description=_("Fee payment for {0}").format(payer_name),
            reference_doctype="Fee Invoice",
            reference_docname=inv.name,
            payer_email=payer_email,
            payer_name=payer_name,
            receipt=inv.name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "student_payment._build_order_payload")
        frappe.throw(
            _("Could not create payment order. Please try again or contact support."),
            frappe.ValidationError,
        )

    return {
        "order_id":            order.get("id"),
        "integration_request": order.get("integration_request"),
        "amount":              order.get("amount"),
        "currency":            order.get("currency", "INR"),
        "key_id":              controller.api_key,
        "payer_name":          payer_name,
        "payer_email":         payer_email,
        "payer_phone":         payer_phone,
        "invoice_name":        inv.name,
        "outstanding":         outstanding,
    }


def _ensure_fee_component():
    """Return the name of a generic 'Program Fee' Fee Component.
    Creates one if it does not already exist.
    """
    existing = frappe.db.get_value(
        "Fee Component",
        {"component_name": "Program Fee"},
        "name",
    )
    if existing:
        return existing

    # Create a generic component so invoices have at least one line item
    comp = frappe.get_doc({
        "doctype":        "Fee Component",
        "component_name": "Program Fee",
        "component_type": "Tuition Fee",
        "amount":         0,
    })
    comp.insert(ignore_permissions=True)
    frappe.db.commit()
    return comp.name


def _create_invoice_from_sm(student_name):
    """Mint a Fee Invoice directly from Student Master fee fields.

    Called when the student has outstanding fees recorded on their SM record
    but no corresponding Fee Invoice has been raised by the admin yet.
    This creates a minimal, single-component invoice so the student can pay.

    Returns the Fee Invoice document.
    """
    sm = frappe.db.get_value(
        "Student Master",
        student_name,
        [
            "total_program_fee", "discount_amount", "scholarship_amount",
            "net_program_fee", "total_paid_amount",
            "programme", "academic_year",
            "first_name", "last_name",
        ],
        as_dict=True,
    ) or {}

    total_fee    = flt(sm.get("total_program_fee") or 0)
    # discount_amount is the calculated scholarship applied to the programme fee.
    # scholarship_amount is the raw admin-entered value (fallback).
    scholarship  = flt(sm.get("discount_amount") or 0) or flt(sm.get("scholarship_amount") or 0)
    already_paid = flt(sm.get("total_paid_amount") or 0)

    if total_fee <= 0:
        frappe.throw(_("No fee amount found on your student record."))

    net = flt(sm.get("net_program_fee") or 0) or max(total_fee - scholarship, 0)
    outstanding = max(net - already_paid, 0)

    if outstanding <= 0:
        frappe.throw(_("No outstanding amount to pay."))

    # Academic context
    enrollment = (
        frappe.db.get_value(
            "Student Enrollment",
            {"student": student_name, "status": "Enrolled"},
            ["name", "academic_year", "term_name", "program"],
            as_dict=True,
            order_by="creation desc",
        )
    )

    fee_component_name = _ensure_fee_component()

    # Build the invoice
    invoice = frappe.get_doc({
        "doctype":          "Fee Invoice",
        "student":          student_name,
        "program":          (enrollment and enrollment.program) or sm.get("programme") or "",
        "academic_year":    (enrollment and enrollment.academic_year) or sm.get("academic_year") or "",
        "academic_term":    (enrollment and enrollment.term_name) or "",
        "enrollment":       (enrollment and enrollment.name) or "",
        "invoice_date":     today(),
        "due_date":         add_days(today(), 30),
        "scholarship_amount": scholarship,
        "fee_components":   [{
            "fee_component":  fee_component_name,
            "component_name": "Program Fee",
            "amount":         total_fee,
            "is_taxable":     0,
            "tax_amount":     0,
            "total_amount":   total_fee,
        }],
    })
    invoice.insert(ignore_permissions=True)

    # Record already-paid amount as a payment entry so the outstanding is correct
    if already_paid > 0:
        # Create a Fee Payment to reflect offline/prior payments
        payment = frappe.get_doc({
            "doctype":        "Fee Payment",
            "fee_invoice":    invoice.name,
            "student":        student_name,
            "payment_date":   today(),
            "payment_mode":   "Bank Transfer",
            "amount":         already_paid,
            "remarks":        "Prior payment recorded from student master",
            "status":         "Draft",
        })
        payment.insert(ignore_permissions=True)
        # submit() triggers FeePayment.on_submit → update_fee_invoice(), which
        # already appends the payment row to invoice.payments and saves it.
        # Do NOT manually append again — that would double-count the payment.
        payment.submit()

    frappe.db.commit()
    invoice.reload()
    return invoice


# ── Public whitelisted endpoints ───────────────────────────────────────────

@frappe.whitelist()
def create_payment_order(invoice_name):
    """Create a Razorpay order for an existing Fee Invoice.

    Validates:
    * Caller is an authenticated student.
    * The invoice belongs to that student (IDOR guard).
    * The invoice has a positive outstanding balance.
    * The invoice is not already Paid or Cancelled.
    """
    student_name = _require_student()
    inv          = _get_owned_invoice(invoice_name, student_name)

    if inv.status in ("Paid", "Cancelled"):
        frappe.throw(_("This invoice is already {0}.").format(inv.status))

    if flt(inv.outstanding_amount) <= 0:
        frappe.throw(_("There is no outstanding amount on this invoice."))

    frappe.db.set_value(
        "Fee Invoice", invoice_name, "payment_status", "Payment Initiated", update_modified=False
    )
    frappe.db.commit()

    controller = _get_razorpay_controller()
    return _build_order_payload(controller, inv, student_name)


@frappe.whitelist()
def ensure_invoice_and_create_order():
    """Ensure the student has a payable Fee Invoice, creating one from their
    Student Master fee data if necessary, then create and return a Razorpay order.

    Called by the PAY NOW button on the Student Master fee fallback card when
    no Fee Invoice exists yet.

    Returns the same dict as create_payment_order().
    """
    student_name = _require_student()

    # Look for an existing unpaid/partially-paid invoice
    existing = frappe.db.get_value(
        "Fee Invoice",
        {
            "student":         student_name,
            "status":          ["not in", ["Paid", "Cancelled"]],
            "outstanding_amount": [">", 0],
        },
        ["name", "student", "student_name", "outstanding_amount",
         "final_payable_amount", "paid_amount", "status"],
        as_dict=True,
        order_by="creation desc",
    )

    if existing:
        inv = existing
    else:
        # Mint a fresh invoice from SM fee fields
        inv_doc = _create_invoice_from_sm(student_name)
        inv = frappe._dict({
            "name":               inv_doc.name,
            "student":            inv_doc.student,
            "student_name":       inv_doc.student_name,
            "outstanding_amount": inv_doc.outstanding_amount,
            "final_payable_amount": inv_doc.final_payable_amount,
            "paid_amount":        inv_doc.paid_amount,
            "status":             inv_doc.status,
        })

    if flt(inv.outstanding_amount) <= 0:
        frappe.throw(_("No outstanding amount to pay."))

    controller = _get_razorpay_controller()
    return _build_order_payload(controller, inv, student_name)


@frappe.whitelist()
def confirm_fee_payment(invoice_name, integration_request,
                        razorpay_payment_id, razorpay_order_id, razorpay_signature):
    """
    Called from the browser after Razorpay's success handler fires.

    Why this exists instead of relying on on_payment_authorized:
    - The payments app's authorize_payment() makes an external HTTP call to Razorpay.
      If that call fails (network, timeout) on_payment_authorized is never reached.
    - on_payment_authorized's exception is silently swallowed, so the JS sees HTTP 200
      and shows "Payment Successful" even though nothing was recorded.

    This endpoint verifies the HMAC-SHA256 signature locally (no external call),
    then idempotently ensures a Fee Payment exists for the invoice.
    """
    student_name = _require_student()
    inv          = _get_owned_invoice(invoice_name, student_name)

    if inv.status == "Paid" or flt(inv.outstanding_amount) <= 0:
        return {
            "status":                "already_paid",
            "invoice_status":        inv.status,
            "paid_amount":           flt(inv.paid_amount),
            "outstanding_amount":    0.0,
            "formatted_paid":        "₹{:,.0f}".format(flt(inv.paid_amount)),
            "formatted_outstanding": "₹0",
        }

    # ── Verify Razorpay HMAC-SHA256 signature locally ─────────────────
    # Signature = HMAC-SHA256(razorpay_order_id + "|" + razorpay_payment_id, secret)
    try:
        controller = frappe.get_doc("Razorpay Settings")
        secret     = controller.get_password(fieldname="api_secret", raise_exception=False) or ""
        if not secret:
            frappe.throw(_("Payment gateway is not configured."), frappe.ValidationError)

        message  = (razorpay_order_id + "|" + razorpay_payment_id).encode("utf-8")
        expected = _hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

        if not _hmac.compare_digest(expected, razorpay_signature):
            frappe.throw(_("Payment signature verification failed."), frappe.PermissionError)
    except (frappe.PermissionError, frappe.ValidationError):
        raise
    except Exception:
        frappe.log_error(frappe.get_traceback(), "confirm_fee_payment: signature check")
        frappe.throw(_("Could not verify payment. Please contact the Bursar's Office."))

    # ── Update Integration Request (best-effort; don't fail if it errors) ─
    try:
        from payments.payment_gateways.doctype.razorpay_settings.razorpay_settings import (
            order_payment_success,
        )
        order_payment_success(
            integration_request,
            _json.dumps({
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_order_id":   razorpay_order_id,
                "razorpay_signature":  razorpay_signature,
            }),
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "confirm_fee_payment: IR update (non-fatal)")

    # ── Idempotently create Fee Payment if on_payment_authorized didn't ─
    existing_fp = frappe.db.get_value(
        "Fee Payment",
        {"fee_invoice": invoice_name, "docstatus": 1},
        "name",
        order_by="creation desc",
    )

    if not existing_fp:
        inv_doc     = frappe.get_doc("Fee Invoice", invoice_name)
        outstanding = flt(inv_doc.outstanding_amount)
        if outstanding > 0:
            fp = frappe.get_doc({
                "doctype":          "Fee Payment",
                "fee_invoice":      invoice_name,
                "student":          student_name,
                "amount":           outstanding,
                "payment_date":     today(),
                "payment_mode":     "Online Payment",
                "reference_number": razorpay_payment_id,
            })
            fp.insert(ignore_permissions=True)
            fp.submit()
            frappe.db.commit()

    # ── Mark gateway payment_status as Captured ───────────────────────
    frappe.db.set_value(
        "Fee Invoice", invoice_name, "payment_status", "Captured", update_modified=False
    )
    frappe.db.commit()

    # ── Return refreshed invoice state ────────────────────────────────
    inv_doc = frappe.get_doc("Fee Invoice", invoice_name)
    return {
        "status":                "success",
        "invoice_status":        inv_doc.status,
        "paid_amount":           flt(inv_doc.paid_amount),
        "outstanding_amount":    max(flt(inv_doc.outstanding_amount), 0),
        "formatted_paid":        "₹{:,.0f}".format(flt(inv_doc.paid_amount)),
        "formatted_outstanding": "₹{:,.0f}".format(max(flt(inv_doc.outstanding_amount), 0)),
    }


# ── Re-Exam payment endpoints ──────────────────────────────────────────────

def _get_owned_registration(registration_name, student_name):
    """Fetch a Re Exam Registration that belongs to *student_name* (IDOR guard)."""
    reg = frappe.db.get_value(
        "Re Exam Registration",
        {"name": registration_name, "student": student_name},
        ["name", "student", "exam_plan", "course", "re_exam_fee", "status"],
        as_dict=True,
    )
    if not reg:
        frappe.throw(
            _("Registration not found or you do not have permission to access it."),
            frappe.PermissionError,
        )
    return reg


def _build_re_exam_order_payload(controller, reg, student_name):
    """Create a Razorpay order for a Re Exam Registration and return the payload dict."""
    sm = frappe.db.get_value(
        "Student Master",
        student_name,
        ["first_name", "last_name", "email", "official_email_id", "phone"],
        as_dict=True,
    ) or {}
    payer_name  = " ".join(filter(None, [sm.get("first_name"), sm.get("last_name")])) or student_name
    payer_email = sm.get("official_email_id") or sm.get("email") or frappe.session.user
    payer_phone = sm.get("phone") or ""

    course_name = frappe.db.get_value("Course", reg.course, "course_name") or reg.course
    fee_amount  = flt(reg.re_exam_fee)

    try:
        order = controller.create_order(
            amount=fee_amount,
            currency="INR",
            title=_("Re-Exam Fee – {0}").format(course_name),
            description=_("Re-examination fee for {0}").format(payer_name),
            reference_doctype="Re Exam Registration",
            reference_docname=reg.name,
            payer_email=payer_email,
            payer_name=payer_name,
            receipt=reg.name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "student_payment._build_re_exam_order_payload")
        frappe.throw(
            _("Could not create payment order. Please try again or contact support."),
            frappe.ValidationError,
        )

    return {
        "order_id":            order.get("id"),
        "integration_request": order.get("integration_request"),
        "amount":              order.get("amount"),
        "currency":            order.get("currency", "INR"),
        "key_id":              controller.api_key,
        "payer_name":          payer_name,
        "payer_email":         payer_email,
        "payer_phone":         payer_phone,
        "registration_name":   reg.name,
        "course_name":         course_name,
    }


@frappe.whitelist()
def create_re_exam_payment_order(exam_plan, course):
    """Create (or retrieve) a Re Exam Registration and return a Razorpay order payload.

    Validates:
    * Caller is an authenticated student with no block override.
    * Re-exam setting exists and deadline has not passed.
    * Fee is > 0 (free registrations use initiate_re_exam_registration instead).
    * Registration is not already Paid.
    """
    student_name = _require_student()

    setting = frappe.db.get_value(
        "Re Exam Course Setting",
        {"exam_plan": exam_plan, "course": course},
        ["name", "re_exam_fee", "deadline_from", "deadline_to"],
        as_dict=True,
    )
    if not setting:
        frappe.throw(_("Re-exam registration is not open for this course yet."))

    if setting.get("deadline_to") and str(setting["deadline_to"]) < today():
        frappe.throw(_("The registration deadline for this course has passed."))

    fee_amount = flt(setting.get("re_exam_fee") or 0)
    if fee_amount <= 0:
        frappe.throw(_("This course has no re-exam fee. Use free registration instead."))

    # Block override check
    override = frappe.db.get_value(
        "Re Exam Student Override",
        {"exam_plan": exam_plan, "course": course, "student": student_name},
        "is_allowed",
    )
    if override is not None and not override:
        frappe.throw(_("You are not allowed to register for this re-examination. Please contact the faculty."))

    # Find or create registration
    existing = frappe.db.get_value(
        "Re Exam Registration",
        {"student": student_name, "exam_plan": exam_plan, "course": course},
        ["name", "status", "re_exam_fee"],
        as_dict=True,
    )

    if existing and existing.status == "Paid":
        frappe.throw(_("You have already paid for this re-examination."))

    if existing and existing.status == "Refunded":
        frappe.throw(_("This registration was refunded. Please contact the administration."))

    if existing and existing.status == "Cancelled":
        frappe.throw(_("This registration has been cancelled. Please contact the administration."))

    if existing:
        reg_name = existing.name
    else:
        doc = frappe.new_doc("Re Exam Registration")
        doc.student     = student_name
        doc.exam_plan   = exam_plan
        doc.course      = course
        doc.re_exam_fee = fee_amount
        doc.status      = "Registered"
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        reg_name = doc.name

    # Mark that the student has opened the payment modal
    frappe.db.set_value(
        "Re Exam Registration", reg_name, "status", "Payment Initiated", update_modified=False
    )
    frappe.db.commit()

    reg = frappe.db.get_value(
        "Re Exam Registration",
        reg_name,
        ["name", "student", "exam_plan", "course", "re_exam_fee", "status"],
        as_dict=True,
    )

    controller = _get_razorpay_controller()
    return _build_re_exam_order_payload(controller, reg, student_name)


@frappe.whitelist()
def confirm_re_exam_payment(registration_name, integration_request,
                             razorpay_payment_id, razorpay_order_id, razorpay_signature):
    """Verify Razorpay HMAC-SHA256 signature and mark Re Exam Registration as Paid.

    Follows the same security model as confirm_fee_payment:
    * Ownership check (IDOR guard).
    * Local HMAC-SHA256 signature verification — no external call.
    * Idempotent: safe to call more than once.
    """
    student_name = _require_student()
    reg = _get_owned_registration(registration_name, student_name)

    if reg.status == "Paid":
        return {"status": "already_paid", "registration_status": "Paid"}

    # Verify signature locally
    try:
        rzp_settings = frappe.get_doc("Razorpay Settings")
        secret = rzp_settings.get_password(fieldname="api_secret", raise_exception=False) or ""
        if not secret:
            frappe.throw(_("Payment gateway is not configured."), frappe.ValidationError)

        message  = (razorpay_order_id + "|" + razorpay_payment_id).encode("utf-8")
        expected = _hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

        if not _hmac.compare_digest(expected, razorpay_signature):
            frappe.throw(_("Payment signature verification failed."), frappe.PermissionError)
    except (frappe.PermissionError, frappe.ValidationError):
        raise
    except Exception:
        frappe.log_error(frappe.get_traceback(), "confirm_re_exam_payment: signature check")
        frappe.throw(_("Could not verify payment. Please contact the administration."))

    # Update Integration Request (best-effort)
    try:
        from payments.payment_gateways.doctype.razorpay_settings.razorpay_settings import (
            order_payment_success,
        )
        order_payment_success(
            integration_request,
            _json.dumps({
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_order_id":   razorpay_order_id,
                "razorpay_signature":  razorpay_signature,
            }),
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "confirm_re_exam_payment: IR update (non-fatal)")

    # Create Re Exam Payment Log (idempotent — webhook may have beaten us to it)
    existing_log = frappe.db.get_value(
        "Re Exam Payment Log",
        {"razorpay_payment_id": razorpay_payment_id},
        "name",
    )
    if not existing_log:
        try:
            reg_for_log = frappe.db.get_value(
                "Re Exam Registration",
                registration_name,
                ["re_exam_fee", "exam_plan", "course"],
                as_dict=True,
            ) or {}
            log_doc = frappe.get_doc({
                "doctype":              "Re Exam Payment Log",
                "re_exam_registration": registration_name,
                "razorpay_payment_id":  razorpay_payment_id,
                "razorpay_order_id":    razorpay_order_id,
                "payment_status":       "Captured",
                "amount":               flt(reg_for_log.get("re_exam_fee") or 0),
                "transaction_date":     frappe.utils.now_datetime(),
                "gateway_response":     _json.dumps({
                    "razorpay_payment_id": razorpay_payment_id,
                    "razorpay_order_id":   razorpay_order_id,
                    "source":             "browser_confirmation",
                }, indent=2),
            })
            log_doc.insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "confirm_re_exam_payment: log creation (non-fatal)")

    # Mark registration as Paid
    frappe.db.set_value(
        "Re Exam Registration",
        registration_name,
        {
            "status":            "Paid",
            "payment_reference": razorpay_payment_id,
        },
        update_modified=True,
    )
    frappe.db.commit()

    return {"status": "success", "registration_status": "Paid"}


@frappe.whitelist()
def get_invoice_summary(invoice_name):
    """Return a lightweight summary of a student's own invoice.
    Used to refresh the fee card after a payment without a full page reload.
    """
    student_name = _require_student()
    inv          = _get_owned_invoice(invoice_name, student_name)

    return {
        "outstanding_amount":    flt(inv.outstanding_amount),
        "paid_amount":           flt(inv.paid_amount),
        "final_payable_amount":  flt(inv.final_payable_amount),
        "status":                inv.status,
        "formatted_outstanding": "₹{:,.0f}".format(flt(inv.outstanding_amount)),
        "formatted_paid":        "₹{:,.0f}".format(flt(inv.paid_amount)),
    }
