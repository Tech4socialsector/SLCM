from html import unescape

import frappe
from frappe import _
from frappe.utils import flt, strip_html


def get_context(context):
    """Pass admission cycle and academic year options to the web form context."""
    pass


# ───────────────────────────────────────────────────────────────────
#  FEE AMOUNT — lookup from Program Reservation Policy
# ───────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False)
def get_application_fee_amount(program, admission_cycle=None, category=None):
    """
    Return the application fee for the given program, admission cycle, and
    reservation category (whether_scstobc_ncl value: NA | SC | ST | OBC-NCL).

    Looks up Program Reservation Policy → Program Reservation Category rows.
    Falls back to the active Admission Cycle when admission_cycle is blank.
    Returns 0 when no matching policy or category row is found.
    """
    if not program:
        return 0
    try:
        cycle = (admission_cycle or "").strip()
        if not cycle:
            cycle = frappe.db.get_value(
                "Admission Cycle", {"status": "Active"}, "name", order_by="creation desc"
            ) or ""
        if not cycle:
            return 0

        from slcm.api.service.application_fee_service import get_application_fee_for_category

        cat = (category or "").strip() or None
        fee = get_application_fee_for_category(program, cycle, cat)
        return flt(fee, 2)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Applicant Web Form — get_application_fee_amount")
        return 0


# ───────────────────────────────────────────────────────────────────
#  SAVE DRAFT
# ───────────────────────────────────────────────────────────────────

@frappe.whitelist()
def save_applicant_draft(data, ignore_mandatory=True):
    """
    Save Applicant record as Draft.

    ignore_mandatory=True  → skip mandatory / validator checks (normal draft save)
    ignore_mandatory=False → enforce all mandatory fields (called before final submit)

    Returns:
      {"status": "success", "name": doc.name, "message": "..."}
      {"status": "error",   "message": "..."}
    """
    # Normalise flag
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
    name  = (data.get("name") or "").strip()

    # Load existing or create new
    if name and frappe.db.exists("Applicant", name):
        doc = frappe.get_doc("Applicant", name)
        if doc.owner != user and (doc.email or "").lower() != (email or "").lower():
            return {"status": "error", "message": _("You do not have permission to edit this application.")}
        current_status = (doc.application_status or "").strip()
        if current_status and current_status != "Draft":
            return {"status": "error", "message": _("Only Draft applications can be saved from the portal.")}
    else:
        doc = frappe.new_doc("Applicant")
        doc.email = email

    # Determine which fields are safe to write
    try:
        meta = frappe.get_meta("Applicant")
    except Exception:
        return {"status": "error", "message": _("Applicant DocType not found.")}

    SKIP_TYPES   = {"Table", "Section Break", "Column Break", "Tab Break", "HTML", "Button"}
    INTERNAL_KEYS = {
        "name", "idx", "doctype", "parent", "parentfield", "parenttype",
        "owner", "creation", "modified", "modified_by", "docstatus",
    }
    valid_scalar  = {f.fieldname for f in meta.fields if f.fieldtype not in SKIP_TYPES}
    child_tables  = {f.fieldname for f in meta.fields if f.fieldtype == "Table"}

    # Apply scalar fields
    for key, value in data.items():
        if key.startswith("__") or key in INTERNAL_KEYS:
            continue
        if key in valid_scalar:
            try:
                setattr(doc, key, value)
            except Exception:
                pass

    # Apply child-table rows
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

    # Enforce safe values
    doc.application_status = "Draft"
    doc.email              = email

    # Recalculate application fee from Program Reservation Policy
    if getattr(doc, "program", None) and getattr(doc, "admission_cycle", None):
        try:
            from slcm.api.service.application_fee_service import get_application_fee_for_category

            raw_cat = (getattr(doc, "whether_scstobc_ncl", "") or "").strip()
            cat     = raw_cat if raw_cat and raw_cat.upper() != "NA" else None
            computed = flt(get_application_fee_for_category(doc.program, doc.admission_cycle, cat), 2)
            fee_status = (getattr(doc, "application_fee_status", "") or "").strip()
            if fee_status not in ("Paid", "Waived"):
                doc.application_fee_amount = computed
        except Exception:
            frappe.log_error(frappe.get_traceback(), "save_applicant_draft — fee recalc")

    doc.flags.ignore_mandatory  = ignore_mandatory
    doc.flags.ignore_permissions = True
    doc.flags.ignore_validate   = ignore_mandatory   # run validators when enforcing mandatory

    try:
        if doc.is_new():
            doc.insert()
        else:
            doc.save()
        frappe.db.commit()
        return {
            "status":  "success",
            "name":    doc.name,
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
        frappe.log_error(frappe.get_traceback(), "save_applicant_draft — Error")
        return {"status": "error", "message": str(e)}


# ───────────────────────────────────────────────────────────────────
#  SUBMIT APPLICANT (called after fee is paid or fee = 0)
# ───────────────────────────────────────────────────────────────────

@frappe.whitelist()
def submit_applicant(applicant_name):
    """
    Final submit: sets application_status = Submitted.
    Must only be called after:
      1. Mandatory validation passes (via save_applicant_draft with ignore_mandatory=False)
      2. Eligibility check passes
      3. Fee is paid/waived (or fee = 0)

    Returns:
      {"status": "success", "name": ..., "application_status": ..., "application_fee_status": ...}
      {"status": "error",   "message": ...}
    """
    if not applicant_name:
        return {"status": "error", "message": _("Applicant name is required.")}

    user = frappe.session.user
    if user == "Guest":
        return {"status": "error", "message": _("You must be logged in.")}

    if not frappe.db.exists("Applicant", applicant_name):
        return {"status": "error", "message": _("Applicant not found.")}

    doc = frappe.get_doc("Applicant", applicant_name)
    email = frappe.db.get_value("User", user, "email") or user

    if doc.owner != user and (doc.email or "").lower() != (email or "").lower():
        return {"status": "error", "message": _("No permission to submit this application.")}

    current_status = (doc.application_status or "").strip()
    if current_status == "Submitted":
        return {
            "status": "success",
            "name": doc.name,
            "application_status": "Submitted",
            "application_fee_status": doc.application_fee_status or "",
            "message": _("Application is already submitted."),
        }

    if current_status and current_status != "Draft":
        return {"status": "error", "message": _("Only Draft applications can be submitted.")}

    # Guard: fee must be paid / waived (or zero)
    fee_amount = flt(doc.application_fee_amount or 0)
    fee_status = (doc.application_fee_status or "").strip()
    if fee_amount > 0 and fee_status not in ("Paid", "Waived"):
        return {"status": "error", "message": _("Application fee must be paid before submitting.")}

    doc.application_status = "Submitted"
    if fee_amount == 0:
        doc.application_fee_status = "Waived"

    doc.flags.ignore_permissions = True
    doc.flags.ignore_mandatory   = False
    doc.flags.ignore_validate    = False

    try:
        doc.save()
        if doc.meta.is_submittable:
            doc.reload()
            doc.submit()
        frappe.db.commit()
        return {
            "status": "success",
            "name": doc.name,
            "application_status": doc.application_status,
            "application_fee_status": doc.application_fee_status or "",
            "message": _("Application submitted successfully."),
        }
    except frappe.ValidationError as e:
        frappe.db.rollback()
        return {"status": "error", "message": str(e)}
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "submit_applicant — Error")
        return {"status": "error", "message": str(e)}


# ───────────────────────────────────────────────────────────────────
#  WEB FORM HOOKS
# ───────────────────────────────────────────────────────────────────

def after_save(doc, context):
    """
    Eligibility is handled via check_eligibility / submit on the portal.
    Avoid running validate_eligibility here — it would frappe.throw HTML and duplicate UI.
    """
    pass


@frappe.whitelist()
def check_eligibility(applicant_name):
    """
    Portal eligibility check for submit flow.

    Returns:
      Eligible: {"status": "Eligible", "message": str}
      Ineligible: {"status": "Ineligible", "failure_reason": str, "suggestions": {...}}
    """
    if not applicant_name:
        return {"status": "Incomplete", "message": ""}

    doc = frappe.get_doc("Applicant", applicant_name)

    if not all([doc.program, doc.campus, doc.admission_cycle, doc.academic_year]):
        return {
            "status": "Incomplete",
            "message": _("Please fill in Program, Campus, Admission Cycle and Academic Year to check eligibility."),
        }

    try:
        doc.flags.skip_eligibility_throw = True
        try:
            doc.validate_eligibility()
        finally:
            doc.flags.skip_eligibility_throw = False

        if (doc.evaluation_status or "").strip() == "Ineligible":
            plain = doc.rejected_reason or ""
            plain = strip_html(plain)
            plain = unescape(plain or "")
            plain = " ".join(plain.split())
            if len(plain) > 2400:
                plain = plain[:2397] + "..."
            suggestions = doc.get_eligibility_suggestion_payload()
            return {
                "status": "Ineligible",
                "message": plain or _("You do not meet the eligibility criteria for the selected program."),
                "failure_reason": plain or _("You do not meet the eligibility criteria for the selected program."),
                "suggestions": suggestions,
            }

        return {
            "status": "Eligible",
            "message": _("You meet the eligibility criteria for the selected program."),
        }
    except frappe.ValidationError as e:
        # Unexpected throw while portal flag was off or from another validation path
        plain = strip_html(str(e))
        plain = unescape(plain or "")
        plain = " ".join(plain.split())
        return {
            "status": "Ineligible",
            "message": plain or _("You do not meet the eligibility criteria for the selected program."),
            "failure_reason": plain or _("You do not meet the eligibility criteria for the selected program."),
            "suggestions": frappe.get_doc("Applicant", applicant_name).get_eligibility_suggestion_payload(),
        }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Web Form — check_eligibility Error")
        return {"status": "Error", "message": _("An error occurred during eligibility check.")}


def _portal_program_row(program, admission_cycle):
    """
    Admission Cycle Program row fields for portal; program_level falls back to
    Program.level_of_study (Program has no program_level field).
    """
    out = {"program_level": None, "intake_type": None, "campus": None}
    program = (program or "").strip()
    admission_cycle = (admission_cycle or "").strip()
    if not program:
        return out
    if admission_cycle:
        acp = frappe.db.get_value(
            "Admission Cycle Program",
            {"parent": admission_cycle, "program": program, "is_active": 1},
            ["intake_type", "program_level", "campus"],
            as_dict=True,
        )
        if acp:
            out["program_level"] = acp.get("program_level")
            out["intake_type"] = acp.get("intake_type")
            out["campus"] = acp.get("campus")
    if not out["program_level"]:
        out["program_level"] = frappe.db.get_value("Program", program, "level_of_study")
    return out


@frappe.whitelist(allow_guest=False)
def get_program_portal_derivatives(program, admission_cycle=None):
    """For web form: when Program (or Admission Cycle) changes, refresh hidden defaults."""
    return _portal_program_row(program or "", admission_cycle or "")


@frappe.whitelist()
def switch_applicant_program(applicant_name, program):
    """
    Switch draft applicant to another same-level eligible program (from evaluation modal).
    """
    program = (program or "").strip()
    if not applicant_name or not program:
        return {"status": "error", "message": _("Program and application are required.")}

    user = frappe.session.user
    if user == "Guest":
        return {"status": "error", "message": _("You must be logged in.")}

    email = frappe.db.get_value("User", user, "email") or user
    doc = frappe.get_doc("Applicant", applicant_name)

    if doc.owner != user and (doc.email or "").lower() != (email or "").lower():
        return {"status": "error", "message": _("You do not have permission to update this application.")}

    st = (doc.application_status or "").strip()
    if st not in ("", "Draft", "Rejected"):
        return {"status": "error", "message": _("Only draft applications can change programme here.")}

    payload = doc.get_eligibility_suggestion_payload()
    allowed = False
    for row in payload.get("programs") or []:
        if row.get("program") == program and not row.get("selected"):
            allowed = True
            break
    if not allowed:
        return {"status": "error", "message": _("This programme is not available to switch to.")}

    if not frappe.db.exists(
        "Admission Cycle Program",
        {"parent": doc.admission_cycle, "program": program, "is_active": 1},
    ):
        return {"status": "error", "message": _("This programme is not open for the current admission cycle.")}

    doc.program = program

    row = _portal_program_row(program, doc.admission_cycle or "")
    if row.get("program_level"):
        doc.program_level = row["program_level"]
    if row.get("intake_type"):
        doc.intake_type = row["intake_type"]
    if row.get("campus"):
        doc.campus = row["campus"]

    doc.evaluation_status = ""
    doc.rejected_reason = ""
    if (doc.application_status or "").strip() == "Rejected":
        doc.application_status = "Draft"

    if doc.program and doc.admission_cycle:
        try:
            from slcm.api.service.application_fee_service import get_application_fee_for_category

            raw_cat = (getattr(doc, "whether_scstobc_ncl", "") or "").strip()
            cat = raw_cat if raw_cat and raw_cat.upper() != "NA" else None
            fee_status = (getattr(doc, "application_fee_status", "") or "").strip()
            if fee_status not in ("Paid", "Waived"):
                doc.application_fee_amount = flt(
                    get_application_fee_for_category(doc.program, doc.admission_cycle, cat), 2
                )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "switch_applicant_program — fee recalc")

    doc.flags.ignore_permissions = True
    doc.flags.ignore_mandatory = True
    doc.flags.ignore_validate = True
    try:
        doc.save()
        frappe.db.commit()
    except Exception as ex:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "switch_applicant_program")
        return {"status": "error", "message": str(ex)}

    return {
        "status": "success",
        "name": doc.name,
        "program": doc.program,
        "program_level": doc.program_level,
        "message": _("Programme updated. You can continue editing your application."),
    }


def _portal_can_access_applicant(applicant_name):
    user = frappe.session.user
    if user == "Guest":
        return False
    email = (frappe.db.get_value("User", user, "email") or user or "").lower()
    row_email = (frappe.db.get_value("Applicant", applicant_name, "email") or "").lower()
    owner = frappe.db.get_value("Applicant", applicant_name, "owner")
    return owner == user or (row_email and row_email == email)


def _latest_application_fee_receipt_for_portal(applicant_name):
    rows = frappe.db.sql(
        """
        SELECT name FROM `tabApplicant Payment Receipt`
        WHERE applicant = %s AND docstatus = 1
        AND IFNULL(offer_letter, '') = ''
        ORDER BY creation DESC
        LIMIT 1
        """,
        applicant_name,
    )
    return rows[0][0] if rows else None


@frappe.whitelist(allow_guest=False)
def portal_application_fee_receipt_ready(applicant_name):
    """Whether the portal may show “Download fee receipt” for this application."""
    applicant_name = (applicant_name or "").strip()
    if not applicant_name or not frappe.db.exists("Applicant", applicant_name):
        return {"ready": False, "receipt_name": ""}
    if not _portal_can_access_applicant(applicant_name):
        frappe.throw(_("Not permitted."), frappe.PermissionError)
    st = (frappe.db.get_value("Applicant", applicant_name, "application_fee_status") or "").strip()
    if st != "Paid":
        return {"ready": False, "receipt_name": ""}
    rname = _latest_application_fee_receipt_for_portal(applicant_name)
    return {"ready": bool(rname), "receipt_name": rname or ""}


@frappe.whitelist(allow_guest=False)
def download_portal_application_fee_receipt(applicant_name):
    """PDF download for the applicant’s application-fee receipt (uses stored Print Format)."""
    applicant_name = (applicant_name or "").strip()
    if not applicant_name or not frappe.db.exists("Applicant", applicant_name):
        frappe.throw(_("Application not found."))
    if not _portal_can_access_applicant(applicant_name):
        frappe.throw(_("Not permitted."), frappe.PermissionError)
    st = (frappe.db.get_value("Applicant", applicant_name, "application_fee_status") or "").strip()
    if st != "Paid":
        frappe.throw(_("Application fee is not paid."))

    receipt_name = _latest_application_fee_receipt_for_portal(applicant_name)
    if not receipt_name:
        frappe.throw(_("Payment receipt not found. Please contact support."))

    receipt = frappe.get_doc(
        "Applicant Payment Receipt", receipt_name, check_permission=False
    )
    fmt = (receipt.payment_receipt_template or "").strip() or None

    # Portal users usually have no Print permission on Applicant Payment Receipt;
    # access is already enforced above via applicant ownership + Paid status.
    prev_ignore = frappe.flags.get("ignore_print_permissions")
    frappe.flags.ignore_print_permissions = True
    try:
        if fmt:
            pdf = frappe.get_print(
                "Applicant Payment Receipt",
                receipt.name,
                print_format=fmt,
                as_pdf=True,
            )
        else:
            pdf = frappe.get_print("Applicant Payment Receipt", receipt.name, as_pdf=True)
    finally:
        if prev_ignore is None:
            frappe.flags.pop("ignore_print_permissions", None)
        else:
            frappe.flags.ignore_print_permissions = prev_ignore

    safe = (receipt.name or "receipt").replace(" ", "-").replace("/", "-")
    frappe.local.response.filename = f"{safe}.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "pdf"
