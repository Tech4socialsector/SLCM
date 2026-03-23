import frappe
from frappe import _
from frappe.utils import flt


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
    """Run eligibility engine after every web form save."""
    try:
        full_doc = frappe.get_doc("Applicant", doc.name)
        full_doc.validate_eligibility()
    except frappe.ValidationError:
        raise
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Web Form — Eligibility Check Error")
        raise


@frappe.whitelist()
def check_eligibility(applicant_name):
    """
    Live eligibility check from JS (debounced).

    Returns:
      {"status": "Eligible"|"Ineligible"|"Incomplete"|"Error", "message": str}
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
        doc.validate_eligibility()
        return {
            "status": "Eligible",
            "message": _("You meet the eligibility criteria for the selected program."),
        }
    except frappe.ValidationError as e:
        return {"status": "Ineligible", "message": str(e)}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Web Form — check_eligibility Error")
        return {"status": "Error", "message": _("An error occurred during eligibility check.")}
