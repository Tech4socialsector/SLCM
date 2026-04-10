import frappe
from frappe import _
from frappe.utils import cint, flt


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
        pc = frappe.get_doc(
            "Applicant Portal Config", "Applicant Portal Config", ignore_permissions=True
        ).as_dict()
    except Exception:
        pc = {}

    user = frappe.session.user or "Guest"
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

    return {
        "banner_image":    ws.get("banner_image") or "",
        "site_title":      ws.get("title") or "SLCM",
        "portal_title":    pc.get("portal_title") or ws.get("title") or "PACE",
        "primary_color":   pc.get("primary_color") or "#1a3c6e",
        "secondary_color": pc.get("secondary_color") or "#c8a14b",
        "footer_address":  pc.get("footer_address") or "",
        "footer_phone":    pc.get("footer_phone") or "",
        "contact_email":   pc.get("contact_email") or pc.get("footer_email") or "",
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
        if current_status and current_status not in ("Draft", ""):
            return {"status": "error", "message": _("Only Draft applications can be saved from the portal.")}
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

    # Enforce Draft status
    try:
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
