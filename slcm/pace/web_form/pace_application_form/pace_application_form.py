import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime


def get_context(context):
    # Hide default breadcrumbs; custom nav injected by pace_application_form.js
    context.no_breadcrumbs = True


# ───────────────────────────────────────────────────────────────────
#  PORTAL SHELL — nav + footer branding (mirrors applicant_form.py)
# ───────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False)
def get_pace_portal_shell_data():
    """
    Return branding + current-user info needed to render the PACE portal nav/footer
    inside the web form. Reads Website Settings and Applicant Portal Config so that
    the PACE form uses the same visual theme as the admission portal.
    """
    ws = frappe.db.get_singles_dict("Website Settings", cast=True) or {}

    try:
        pc = frappe.get_doc(  # pyright: ignore[reportCallIssue]
            "Applicant Portal Config", "Applicant Portal Config", ignore_permissions=True
        ).as_dict()
    except Exception:
        pc = {}

    user = frappe.session.user or "Guest"
    full_name = ""
    user_image = ""
    first_name, middle_name, last_name, email = "", "", "", ""
    if user and user != "Guest":
        uinfo = frappe.db.get_value(
            "User", user, ["full_name", "user_image", "first_name", "middle_name", "last_name", "email"], as_dict=True
        ) or {}
        full_name = uinfo.get("full_name") or user
        user_image = uinfo.get("user_image") or ""
        first_name = uinfo.get("first_name") or ""
        middle_name = uinfo.get("middle_name") or ""
        last_name = uinfo.get("last_name") or ""
        email = uinfo.get("email") or ""

    pace_enabled = int(pc.get("enable_pace_admission") or 0) if pc else 0
    powerd_by = (pc.get("powerd_by") or "boscosoft") if pc else "boscosoft"

    programmes = frappe.db.sql(
        """
        SELECT
            COALESCE(cp.program_name, p.program_name, cp.program) AS name,
            COALESCE(p.program_slug, cp.program) AS slug
        FROM `tabAdmission Cycle Program` cp
        LEFT JOIN `tabProgram` p ON p.name = cp.program
        WHERE cp.parent = (
            SELECT name FROM `tabAdmission Cycle`
            WHERE status = 'Active' LIMIT 1
        )
        LIMIT 5
    """,
        as_dict=True,
    )

    if not programmes:
        programmes = frappe.db.sql(
            """
            SELECT program_name AS name, COALESCE(program_slug, name) AS slug
            FROM `tabProgram`
            WHERE program_status = 'Active' OR program_status IS NULL
            LIMIT 5
        """,
            as_dict=True,
        )

    return {
        "banner_image":    ws.get("banner_image") or "",
        "site_title":      ws.get("title") or "SLCM",
        "portal_title":    pc.get("portal_title") or ws.get("title") or "Admissions",
        "primary_color":   pc.get("primary_color") or "#1a3c6e",
        "secondary_color": pc.get("secondary_color") or "#c8a14b",
        "footer_address":  pc.get("footer_address") or "",
        "footer_phone":    pc.get("footer_phone") or "",
        "contact_email":   pc.get("contact_email") or pc.get("footer_email") or "",
        "programmes":      [{"name": p.get("name", ""), "slug": p.get("slug", "")} for p in (programmes or [])],
        "pace_enabled":    pace_enabled,
        "powerd_by":       powerd_by,
        "user":            user,
        "full_name":       full_name,
        "first_name":      first_name,
        "middle_name":     middle_name,
        "last_name":       last_name,
        "email":           email,
        "user_image":      user_image,
        "is_guest":        user == "Guest",
    }


# ───────────────────────────────────────────────────────────────────
#  SAVE DRAFT — PACE Application
# ───────────────────────────────────────────────────────────────────

@frappe.whitelist()
def save_pace_draft(data, ignore_mandatory=True):
    """
    Save a PACE Application record as Draft.

    ignore_mandatory=True  → skip mandatory checks (normal draft save)
    ignore_mandatory=False → enforce mandatory fields (called before final submit)

    Returns:
      {"status": "success", "name": doc.name, "message": "..."}
      {"status": "error",   "message": "..."}
    """
    if isinstance(ignore_mandatory, str):
        ignore_mandatory = frappe.parse_json(ignore_mandatory)
    ignore_mandatory = bool(ignore_mandatory)

    if isinstance(data, str):
        data = frappe.parse_json(data)
    if not isinstance(data, dict) or not data:
        return {"status": "error", "message": _("No data provided.")}

    user = frappe.session.user
    if user == "Guest":
        return {"status": "error", "message": _("You must be logged in to save a draft.")}

    email = frappe.db.get_value("User", user, "email") or user
    name = (data.get("name") or "").strip()

    # Load existing or create new
    if name and frappe.db.exists("PACE Application", name):
        doc = frappe.get_doc("PACE Application", name)
        if doc.owner != user and (getattr(doc, "email_address", "") or "").lower() != (email or "").lower():
            return {"status": "error", "message": _("You do not have permission to edit this application.")}
        current_status = (getattr(doc, "status", "") or "").strip()
        if current_status and current_status not in ("Draft", "Returned for Correction", ""):
            return {"status": "error", "message": _("Only Draft or Returned for Correction applications can be saved from the portal.")}
    else:
        doc = frappe.new_doc("PACE Application")
        try:
            doc.email_address = email
        except Exception:
            pass

    # Determine which fields are writable
    try:
        meta = frappe.get_meta("PACE Application")
    except Exception:
        return {"status": "error", "message": _("PACE Application DocType not found.")}

    SKIP_TYPES = {"Table", "Section Break", "Column Break", "Tab Break", "HTML", "Button"}
    INTERNAL_KEYS = {
        "name", "idx", "doctype", "parent", "parentfield", "parenttype",
        "owner", "creation", "modified", "modified_by", "docstatus",
    }
    valid_scalar = {f.fieldname for f in meta.fields if f.fieldtype not in SKIP_TYPES}
    child_tables = {f.fieldname for f in meta.fields if f.fieldtype == "Table"}

    for key, value in data.items():
        if key.startswith("__") or key in INTERNAL_KEYS:
            continue
        if key in valid_scalar:
            try:
                setattr(doc, key, value)
            except Exception:
                pass

    for ct_field in child_tables:
        rows = data.get(ct_field)
        if not isinstance(rows, list):
            continue
        doc.set(ct_field, [])
        for row in rows:
            if isinstance(row, dict):
                clean = {k: v for k, v in row.items() if k not in INTERNAL_KEYS and not k.startswith("__")}
                try:
                    doc.append(ct_field, clean)
                except Exception:
                    pass

    # Enforce status
    try:
        if doc.status != "Returned for Correction":
            doc.status = "Draft"
    except Exception:
        pass

    doc.flags.ignore_mandatory = ignore_mandatory
    doc.flags.ignore_permissions = True
    doc.flags.ignore_validate = ignore_mandatory

    if not doc.is_new():
        doc.flags.ignore_validate_update_after_submit = True

    try:
        if doc.is_new():
            doc.insert()
        else:
            doc.save()
        frappe.db.commit()
        return {
            "status": "success",
            "name": doc.name,
            "message": _("Draft saved successfully."),
        }
    except frappe.MandatoryError as e:
        frappe.db.rollback()
        return {"status": "error", "message": _("Required fields missing: {0}").format(str(e))}
    except frappe.ValidationError as e:
        frappe.db.rollback()
        return {"status": "error", "message": str(e)}
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "save_pace_draft — Error")
        return {"status": "error", "message": str(e)}

# ───────────────────────────────────────────────────────────────────
#  AUTO-FETCH PREVIOUS APPLICATION INFO
# ───────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_old_pace_application():
    """
    Fetch the most recent PACE application for the current user to auto-fill
    the form. Specifically exclude attachments, programme, academic_year, and 
    internal status-related fields.
    """
    user = frappe.session.user
    if user == "Guest":
        return {}

    email = frappe.db.get_value("User", user, "email") or user

    # Find the most recently created application for this email/owner
    old_app_name = frappe.db.get_value(
        "PACE Application", 
        {"email_address": email}, 
        "name", 
        order_by="creation desc"
    )

    if not old_app_name:
        return {}

    old_app = frappe.get_doc("PACE Application", old_app_name).as_dict()

    # We want to keep personal details, education history, work experience, etc.
    # Exclude system/state/payment/document fields
    exclude_fields = {
        "name", "owner", "creation", "modified", "modified_by", "docstatus",
        "idx", "status", "programme", "academic_year", 
        "upload_student_photo"
    }

    # Also dynamically exclude Attach and Attach Image fields
    meta = frappe.get_meta("PACE Application")
    for df in meta.fields:
        if df.fieldtype in ["Attach", "Attach Image"]:
            exclude_fields.add(df.fieldname)

    result = {}
    for key, value in old_app.items():
        if key not in exclude_fields and not key.startswith("__"):
            # If it's a child table, safely pass it avoiding its __ internals
            if isinstance(value, list) and value and isinstance(value[0], dict):
                clean_lines = []
                for row in value:
                    clean_row = {
                        k: v for k, v in row.items() 
                        if k not in ["name", "parent", "parentfield", "parenttype", "doctype", "creation", "modified", "modified_by", "docstatus", "idx"]
                    }
                    clean_lines.append(clean_row)
                result[key] = clean_lines
            else:
                result[key] = value

    return result

@frappe.whitelist()
def check_existing_pace_application(programme, academic_year=None):
    """
    Check if the user has already started or submitted an application for the
    specifically requested programme.
    Returns the application name and its status if found.
    """
    user = frappe.session.user
    if user == "Guest" or not programme:
        return None

    email = frappe.db.get_value("User", user, "email") or user
    
    filters = {"email_address": email, "programme": programme}
    if academic_year:
        filters["academic_year"] = academic_year

    # Find ANY application for this prog
    existing = frappe.db.get_value(
        "PACE Application", 
        filters, 
        ["name", "status"], 
        as_dict=True, 
        order_by="creation desc"
    )

    return existing

@frappe.whitelist()
def get_pace_admission_fee(application):
    """
    Get the application fee for a PACE application.
    `application` may be:
      - a doc name string  → loaded from DB
      - a JSON/dict object → used as-is (fallback from JS before save)
      - a Frappe Document  → used directly
    """
    import json as _json

    # --- normalise input ---
    if isinstance(application, str):
        # could be a doc name OR a JSON string passed from JS
        try:
            parsed = _json.loads(application)
            if isinstance(parsed, dict):
                application = parsed          # treat as plain dict
            else:
                application = frappe.get_doc("PACE Application", application)
        except (_json.JSONDecodeError, ValueError):
            application = frappe.get_doc("PACE Application", application)

    # --- pull fields regardless of whether it is a dict or a doc ---
    def _get(obj, field):
        if isinstance(obj, dict):
            return obj.get(field)
        return getattr(obj, field, None)

    programme    = _get(application, "programme")
    academic_year = _get(application, "academic_year")
    nationality  = (_get(application, "nationality") or "").strip()

    if not programme or not academic_year:
        return {"fee": 0, "reason": "missing programme or academic_year"}

    # --- find active PACE Admission for this academic year ---
    admission_name = frappe.db.get_value(
        "PACE Admission",
        {"academic_year": academic_year, "status": "Active"},
        "name"
    )

    if not admission_name:
        # Fallback: any PACE Admission for this year
        admission_name = frappe.db.get_value(
            "PACE Admission",
            {"academic_year": academic_year},
            "name",
            order_by="creation desc"
        )

    if not admission_name:
        return {"fee": 0, "reason": "no PACE Admission for academic_year"}

    admission_doc = frappe.get_doc("PACE Admission", admission_name)
    gateway  = admission_doc.payment_gateway
    template = admission_doc.payment_receipt_template
    fee = 0

    for p in admission_doc.programmes:
        if p.programme == programme:
            if nationality == "Indian":
                fee = flt(p.get("application_fee_indian") or 0)
            else:
                fee = flt(p.get("application_fee_foreign") or 0)
            break

    return {
        "fee": fee,
        "gateway": gateway,
        "template": template,
        "admission": admission_name
    }

@frappe.whitelist()
def initiate_pace_payment(application_name):
    application = frappe.get_doc("PACE Application", application_name)
    fee_info = get_pace_admission_fee(application)
    amount = flt(fee_info.get("fee"))
    
    if amount <= 0:
        # No fee, directly submit?
        application.status = "Submitted"
        application.save(ignore_permissions=True)
        return {"status": "success", "message": "Application submitted."}
        
    # Check if assignment already exists
    assignment_name = frappe.db.get_value("PACE Applicant Fee Assignment", {
        "applicant": application_name,
        "fee_type": "Application Fee",
        "status": ["!=", "Cancelled"]
    })
    
    if assignment_name:
        assignment = frappe.get_doc("PACE Applicant Fee Assignment", assignment_name)
    else:
        assignment = frappe.new_doc("PACE Applicant Fee Assignment")
        assignment.applicant = application_name
        assignment.fee_type = "Application Fee"
        assignment.program = application.programme
        assignment.academic_year = application.academic_year
        assignment.currency = "INR"
        assignment.total_amount = amount
        assignment.final_payable_amount = amount
        assignment.insert(ignore_permissions=True)
        
    # Check if payment request exists
    pr_name = frappe.db.get_value("Payment Request", {
        "reference_doctype": "PACE Applicant Fee Assignment",
        "reference_name": assignment.name,
        "docstatus": ["!=", 2]
    })
    
    if pr_name:
        pr = frappe.get_doc("Payment Request", pr_name)
        if pr.status == "Paid":
            return {"status": "paid", "message": "Already paid."}
    else:
        try:
            from payments.utils import get_payment_gateway_controller
        except ImportError:
            try:
                from frappe.integrations.utils import get_payment_gateway_controller
            except ImportError:
                pass
        
        pr = frappe.new_doc("Payment Request")
        pr.payment_gateway = fee_info.get("gateway")
        pr.payment_request_type = "Outward" # Or Inward? Usually Inward for receiving money. Frappe uses 'Inward' for receiving.
        pr.payment_request_type = "Inward"
        pr.currency = "INR"
        pr.amount = amount
        pr.reference_doctype = "PACE Applicant Fee Assignment"
        pr.reference_name = assignment.name
        pr.submit_doc = 1
        pr.email_to = application.email_address
        pr.subject = _("Application Fee for {0}").format(application.programme)
        pr.insert(ignore_permissions=True)
        pr.submit()
        
    # Generate the URL specifically for the payment-request page
    # which handles session/CSRF tokens more gracefully than direct API calls
    payment_url = f"/payment-request?name={pr.name}"
    from frappe.utils import get_url
    payment_url = get_url(payment_url)
        
    return {
        "status": "pending",
        "payment_request": pr.name,
        "payment_url": payment_url
    }

@frappe.whitelist()
def initiate_pace_razorpay_order(application_name):
    """
    Creates/Gets Fee Assignment and links it to a Payment Request.
    """
    application = frappe.get_doc("PACE Application", application_name)

    # 1. Calculate fee
    fee_info = get_pace_admission_fee(application_name)
    amount = flt(fee_info.get("fee") or 0)

    if amount <= 0:
        frappe.db.set_value("PACE Application", application_name, "status", "Submitted")
        return {"status": "free", "message": _("Application submitted (no fee required).")}

    # 2. Get or create Fee Assignment (Single record)
    assignment_name = frappe.db.get_value(
        "PACE Applicant Fee Assignment",
        {"applicant": application_name, "status": ["!=", "Cancelled"]},
        "name"
    )

    if assignment_name:
        assignment = frappe.get_doc("PACE Applicant Fee Assignment", assignment_name)
        # Update amount if it changed (e.g. nationality changed before submit)
        if flt(assignment.total_amount) != amount or assignment.status == "Draft":
            assignment.total_amount = amount
            assignment.final_payable_amount = amount
            assignment.status = "Assigned"
            assignment.save(ignore_permissions=True)
    else:
        assignment = frappe.new_doc("PACE Applicant Fee Assignment")
        assignment.applicant = application_name
        assignment.fee_type = "Application Fee"
        assignment.program = application.programme
        assignment.academic_year = application.academic_year
        assignment.admission_cycle = fee_info.get("admission")
        assignment.currency = "INR"
        assignment.total_amount = amount
        assignment.final_payable_amount = amount
        assignment.status = "Assigned"
        assignment.insert(ignore_permissions=True)
        assignment.save(ignore_permissions=True)

    if assignment.status == "Paid":
        frappe.db.set_value("PACE Application", application_name, "status", "Submitted")
        return {"status": "already_paid", "message": _("Fee already paid.")}

    # 3. Get or create Payment Request
    pr_name = frappe.db.get_value("Payment Request", {
        "reference_doctype": "PACE Applicant Fee Assignment",
        "reference_name": assignment.name,
        "docstatus": ["!=", 2]
    })

    pr = None
    if pr_name:
        pr = frappe.get_doc("Payment Request", pr_name)
        # If amount changed, cancel old PR and create new one
        if flt(pr.amount) != amount:
            pr.flags.ignore_permissions = True
            pr.cancel()
            pr = None

    gateway = fee_info.get("gateway") or "Razorpay"
    from payments.utils import get_payment_gateway_controller
    controller = get_payment_gateway_controller(gateway)

    if not pr:
        pr = frappe.new_doc("Payment Request")
        pr.payment_gateway = gateway
        pr.currency = "INR"
        pr.amount = amount
        pr.email_to = application.email_address
        pr.subject = _("Application Fee for {0}").format(application.programme)
        pr.reference_doctype = "PACE Applicant Fee Assignment"
        pr.reference_name = assignment.name
        pr.flags.ignore_permissions = True
        pr.insert(ignore_permissions=True)
        pr.submit()

    # 4. Get Razorpay Order ID
    if not pr.transaction_id:
        payment_details = {
            "amount": amount,
            "currency": "INR",
            "receipt": pr.name,
            "description": pr.subject
        }
        order = controller.create_order(**payment_details)
        pr.db_set("transaction_id", order.get("id"))

    # Fetch API Key from settings
    settings = frappe.get_doc("Razorpay Settings")
    
    # Commit changes to ensure Assignment and Payment Request are stored permanently
    frappe.db.commit()

    return {
        "order_id": pr.transaction_id,
        "key_id": settings.api_key,
        "amount": pr.amount * 100, # Razorpay expects paise
        "currency": pr.currency,
        "assignment": assignment.name,
        "payment_request": pr.name
    }


@frappe.whitelist()
def verify_pace_payment_signature(razorpay_payment_id, razorpay_order_id, razorpay_signature, assignment_name):
    """
    Verifies the Razorpay signature then finalises the assignment and payment request.

    Note: ``PACE Applicant Fee Assignment`` has no ``on_payment_authorized`` hook (that call
    caused every post-payment verify to fail with AttributeError). Logic matches
    ``slcm.pace.api.verify_pace_payment`` but keeps the web-form outcome of setting the
    application to *Submitted* instead of *Fee Paid*.
    """
    try:
        assignment = frappe.get_doc("PACE Applicant Fee Assignment", assignment_name)

        # Order id is stored on PR as transaction_id in initiate_pace_razorpay_order; some flows set razorpay_order_id.
        pr_name = frappe.db.get_value(
            "Payment Request",
            {
                "reference_doctype": "PACE Applicant Fee Assignment",
                "reference_name": assignment.name,
                "docstatus": 1,
                "transaction_id": razorpay_order_id,
            },
            "name",
        )
        if not pr_name:
            pr_name = frappe.db.get_value(
                "Payment Request",
                {
                    "reference_doctype": "PACE Applicant Fee Assignment",
                    "reference_name": assignment.name,
                    "docstatus": 1,
                    "razorpay_order_id": razorpay_order_id,
                },
                "name",
            )
        if not pr_name:
            pr_name = frappe.db.get_value(
                "Payment Request",
                {
                    "reference_doctype": "PACE Applicant Fee Assignment",
                    "reference_name": assignment.name,
                    "docstatus": 1,
                },
                "name",
                order_by="creation desc",
            )
        if not pr_name:
            return {"status": "failed", "message": _("No Payment Request found for this assignment.")}

        pr = frappe.get_doc("Payment Request", pr_name)
        gateway = pr.payment_gateway or frappe.db.get_value("Payment Gateway", {"is_default": 1}, "name") or "Razorpay"

        from payments.utils import get_payment_gateway_controller
        from slcm.pace.api import _update_pace_payment_request

        controller = get_payment_gateway_controller(gateway)
        api_secret = controller.get_password("api_secret")
        body = razorpay_order_id + "|" + razorpay_payment_id
        controller.verify_signature(body, razorpay_signature, api_secret)

        assignment.status = "Paid"
        assignment.transaction_id = razorpay_payment_id
        assignment.payment_date = now_datetime().date()
        assignment.flags.ignore_permissions = True
        assignment.save(ignore_permissions=True)

        _update_pace_payment_request(
            assignment,
            gateway,
            razorpay_order_id,
            "Paid",
            razorpay_payment_id,
            response_data={"payment_id": razorpay_payment_id, "signature": razorpay_signature},
        )

        app = frappe.get_doc("PACE Application", assignment.applicant)
        app.status = "Submitted"
        app.flags.ignore_permissions = True
        app.save(ignore_permissions=True)

        frappe.db.commit()
        return {"status": "success"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "PACE Payment Verification Failed")
        return {"status": "failed", "message": str(e)}

@frappe.whitelist()
def update_application_status_after_payment(application_name):
    application = frappe.get_doc("PACE Application", application_name)
    
    # Check if payment is successful
    paid = frappe.db.exists("Payment Request", {
        "reference_doctype": "PACE Applicant Fee Assignment",
        "reference_name": ["in", frappe.get_all("PACE Applicant Fee Assignment", {"applicant": application_name}, "name")],
        "status": "Paid"
    })
    
    if paid:
        application.status = "Submitted"
        application.save(ignore_permissions=True)
        # Also create receipt
        generate_pace_receipt(application_name)
        return {"status": "success"}
    
    return {"status": "pending"}

@frappe.whitelist()
def generate_pace_receipt(application_name):
    application = frappe.get_doc("PACE Application", application_name)
    
    # Check if already exists
    if frappe.db.exists("PACE Receipt", {"pace_application": application_name, "fee_type": "Application Fee"}):
        return frappe.db.get_value("PACE Receipt", {"pace_application": application_name, "fee_type": "Application Fee"}, "name")
        
    assignment_name = frappe.db.get_value("PACE Applicant Fee Assignment", {
        "applicant": application_name,
        "fee_type": "Application Fee",
        "status": "Paid"
    })
    
    if not assignment_name:
        # Check if partially paid or search via payment request
        pr = frappe.get_all("Payment Request", {
            "reference_doctype": "PACE Applicant Fee Assignment",
            "reference_name": ["in", frappe.get_all("PACE Applicant Fee Assignment", {"applicant": application_name}, "name")],
            "status": "Paid"
        }, ["name", "reference_name", "creation", "transaction_id"])
        
        if not pr:
            return None
            
        assignment_name = pr[0].reference_name
        transaction_id = pr[0].transaction_id
        payment_date = pr[0].creation
    else:
        assignment = frappe.get_doc("PACE Applicant Fee Assignment", assignment_name)
        transaction_id = assignment.transaction_id
        payment_date = assignment.payment_date or assignment.modified
        
    receipt = frappe.new_doc("PACE Receipt")
    receipt.pace_application = application_name
    receipt.fee_assignment = assignment_name
    receipt.program = application.programme
    receipt.academic_year = application.academic_year
    receipt.fee_type = "Application Fee"
    receipt.amount = frappe.db.get_value("PACE Applicant Fee Assignment", assignment_name, "total_amount")
    receipt.currency = "INR"
    receipt.transaction_id = transaction_id
    receipt.payment_date = payment_date
    receipt.insert(ignore_permissions=True)
    
    return receipt.name

@frappe.whitelist()
def get_restricted_fields(application_name):
    verification = frappe.db.get_value("PACE Document Verification", {"application": application_name}, "name")
    if not verification:
        return []
        
    doc = frappe.get_doc("PACE Document Verification", verification)
    
    fields = []
    for item in doc.verification_items:
        if item.status == "Returned for Correction" and item.fieldname:
            fields.append(item.fieldname)
            
    return fields
