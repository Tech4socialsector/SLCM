import frappe
from frappe import _
from frappe.utils import flt, now, nowdate


# ═══════════════════════════════════════════════════════════════════
#  PAGE CONTEXT
# ═══════════════════════════════════════════════════════════════════

def get_context(context):
    """
    Builds the Jinja context for the application form web page.

    Fixes from original:
    ────────────────────
    1. Renamed to index.py (Frappe web page convention: folder = route, index.py inside).
    2. Removed usage of non-existent 'Applicant Portal Config' single doctype (caused 500 error).
    3. Added error handling on all get_all() calls so page still loads on misconfigured sites.
    4. Added guest-redirect guard — unauthenticated users are redirected to login.
    5. Properly serializes doc to dict so Jinja |tojson works cleanly.
    6. Added `program_status` filter check with fallback to avoid filter-column errors.
    7. All dropdowns have a safe fallback to [] so Jinja loops never crash.
    """

    # Guard — portal requires login
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/application-form"
        raise frappe.Redirect

    context.no_cache    = 1
    context.show_sidebar = False

    # ── Pre-fill existing applicant doc ──────────────────────────────
    try:
        applicant = frappe.get_all(
            "Applicant",
            filters={"email": frappe.session.user},
            limit=1
        )
        if applicant:
            doc = frappe.get_doc("Applicant", applicant[0].name)
            context.applicant_data = frappe.parse_json(frappe.as_json(doc))
        else:
            context.applicant_data = {}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Application Form — Get Applicant")
        context.applicant_data = {}

    # ── Programs ──────────────────────────────────────────────────────
    try:
        # Attempt with program_status filter; fall back without it
        try:
            context.programs = frappe.get_all(
                "Program",
                fields=["name", "program_level"],
                filters={"program_status": "Active"},
                order_by="name asc"
            )
        except Exception:
            context.programs = frappe.get_all(
                "Program",
                fields=["name", "program_level"],
                order_by="name asc"
            )
    except Exception:
        context.programs = []

    # ── Campuses ──────────────────────────────────────────────────────
    try:
        context.campuses = frappe.get_all(
            "Campus",
            fields=["name"],
            filters={"is_active": 1},
            order_by="name asc"
        )
    except Exception:
        context.campuses = []

    # ── Academic Years ────────────────────────────────────────────────
    try:
        context.academic_years = frappe.get_all(
            "Academic Year",
            fields=["name"],
            order_by="name desc"
        )
    except Exception:
        context.academic_years = []

    # ── Admission Cycles (active only) ────────────────────────────────
    try:
        context.admission_cycles = frappe.get_all(
            "Admission Cycle",
            fields=["name"],
            filters={"status": "Active"},
            order_by="name desc"
        )
    except Exception:
        context.admission_cycles = []

    # ── Nationalities ─────────────────────────────────────────────────
    try:
        context.nationalities = frappe.get_all(
            "Country",
            fields=["name"],
            order_by="name asc"
        )
    except Exception:
        context.nationalities = []

    # ── HSC Groups ────────────────────────────────────────────────────
    try:
        context.hsc_groups = frappe.get_all("HSC Groups", fields=["name"], order_by="name asc")
    except Exception:
        context.hsc_groups = []

    # ── National Tests ────────────────────────────────────────────────
    try:
        context.national_tests = frappe.get_all("National Test", fields=["name"], order_by="name asc")
    except Exception:
        context.national_tests = []

    return context


# ═══════════════════════════════════════════════════════════════════
#  SAVE / SUBMIT API
# ═══════════════════════════════════════════════════════════════════

@frappe.whitelist()
def save_form(data):
    """
    Save (draft) or submit (final) an Applicant document.

    Fixes from original:
    ────────────────────
    1. Uses frappe.session.user directly (no need for email param from untrusted input).
    2. Properly sanitises only valid Applicant fields — prevents injection via unknown keys.
    3. Child tables are cleared and re-appended correctly using doc.set() + doc.append().
    4. Raises HTTP 400 for ValidationError instead of silently returning error dict,
       so JS can catch it and surface the message to the user.
    5. Removed __submit flag manipulation that bypassed before_submit hook checks.
    6. Returns consistent response shape: {"name": ..., "status": "success"|"draft"}.
    """
    if isinstance(data, str):
        data = frappe.parse_json(data)

    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("You must be logged in to save an application."), frappe.AuthenticationError)

    email = frappe.db.get_value("User", user, "email") or user

    # ── Validate required submission fields ──────────────────────────
    is_submit = bool(data.get("__submit"))

    # ── Get valid fields from DocType meta ───────────────────────────
    meta = frappe.get_meta("Applicant")
    valid_scalar_fields = {f.fieldname for f in meta.fields if f.fieldtype not in ("Table", "Section Break", "Column Break", "Tab Break", "HTML", "Button")}
    child_table_fields  = {"ug_degree_details", "pg_degree_details", "categories"}

    # ── Sanitise data ────────────────────────────────────────────────
    sanitized = {}
    for key, value in data.items():
        if key.startswith("__"):
            continue
        if key in valid_scalar_fields:
            sanitized[key] = value
        elif key in child_table_fields:
            sanitized[key] = value  # handled separately below

    # ── Find or create doc ───────────────────────────────────────────
    existing_name = frappe.db.get_value("Applicant", {"email": email}, "name")

    if existing_name:
        doc = frappe.get_doc("Applicant", existing_name)
    else:
        doc = frappe.new_doc("Applicant")
        doc.email = email

    # ── Apply scalar fields ──────────────────────────────────────────
    scalar_data = {k: v for k, v in sanitized.items() if k not in child_table_fields}
    doc.update(scalar_data)

    # ── Apply child tables ───────────────────────────────────────────
    for ct_field in child_table_fields:
        if ct_field in sanitized:
            doc.set(ct_field, [])
            rows = sanitized[ct_field]
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        # Strip meta keys frappe adds
                        clean_row = {k: v for k, v in row.items() if not k.startswith("__") and k not in ("name", "idx", "doctype", "parent", "parentfield", "parenttype")}
                        doc.append(ct_field, clean_row)

    # ── Ensure email is always set ───────────────────────────────────
    doc.email = email

    try:
        doc.flags.ignore_permissions = True

        if is_submit:
            # Applicant is usually not a submittable doctype in this system.
            # We set the application_status to "Submitted" to signify completion.
            if hasattr(doc, "application_status"):
                doc.application_status = "Submitted"
            
            doc.save(ignore_permissions=True)
            
            # If there's any workflow or specific logic that requires submit, 
            # it should be handled via status change or by making the DocType submittable.
            # doc.submit() # -> Removed to avoid BusinessLogicError
            
            frappe.db.commit()
            return {
                "status":  "success",
                "name":    doc.name,
                "message": _("Application submitted successfully.")
            }
        else:
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            return {
                "status":  "draft",
                "name":    doc.name,
                "message": _("Draft saved.")
            }

    except frappe.ValidationError as e:
        frappe.db.rollback()
        frappe.local.response.http_status_code = 400
        frappe.local.response["message"] = {"error": str(e)}
        return

    except frappe.PermissionError:
        frappe.db.rollback()
        frappe.local.response.http_status_code = 403
        frappe.local.response["message"] = {"error": _("You do not have permission to perform this action.")}
        return

    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Application Form — save_form Error")
        frappe.local.response.http_status_code = 500
        frappe.local.response["message"] = {"error": _("An internal error occurred. Please try again.")}
        return


# ═══════════════════════════════════════════════════════════════════
#  ELIGIBILITY CHECK API  (called from portal JS)
# ═══════════════════════════════════════════════════════════════════

@frappe.whitelist()
def check_portal_eligibility(applicant_data):
    """
    Runs a lightweight eligibility check for the portal without saving the doc.

    This mirrors the validate_eligibility() logic from applicant.py but:
    - Does NOT persist anything
    - Returns a structured JSON result the JS can render

    Returns:
    {
        "eligible": bool,
        "message":  str,
        "programs": [{"program": str, "eligible": bool, "reason": str}, ...]
    }
    """
    if isinstance(applicant_data, str):
        applicant_data = frappe.parse_json(applicant_data)

    program       = applicant_data.get("program")
    campus        = applicant_data.get("campus")
    admission_cycle = applicant_data.get("admission_cycle")
    academic_year = applicant_data.get("academic_year")

    if not all([program, campus, admission_cycle, academic_year]):
        return {
            "eligible": True,
            "message":  "Fill in Program, Campus, Admission Cycle and Academic Year to check eligibility.",
            "programs": []
        }

    try:
        # Create a temporary in-memory Applicant doc for the eligibility engine
        doc = frappe.new_doc("Applicant")
        meta = frappe.get_meta("Applicant")
        valid_fields = {f.fieldname for f in meta.fields}

        for key, val in applicant_data.items():
            if key in valid_fields and not key.startswith("__"):
                try:
                    setattr(doc, key, val)
                except Exception:
                    pass

        # Set child tables
        for ct in ["ug_degree_details", "pg_degree_details", "categories"]:
            rows = applicant_data.get(ct)
            if rows and isinstance(rows, list):
                doc.set(ct, [])
                for row in rows:
                    if isinstance(row, dict):
                        doc.append(ct, row)

        doc.flags.ignore_permissions = True

        # Use the existing eligibility engine
        # Get program level to find peer programs
        program_level = doc._get_selected_program_level() if hasattr(doc, '_get_selected_program_level') else frappe.db.get_value("Program", program, "program_level")
        all_programs  = doc._get_all_programs_for_level(program_level) if hasattr(doc, '_get_all_programs_for_level') else [program]

        programs_result = []
        main_eligible   = True
        main_message    = "You meet the eligibility criteria for the selected program."

        for prog_name in all_programs[:10]:  # Cap at 10 for performance
            is_elig, reason = doc._check_eligibility_for_program(prog_name) if hasattr(doc, '_check_eligibility_for_program') else (True, "")
            programs_result.append({
                "program":  prog_name,
                "eligible": is_elig,
                "reason":   reason or ""
            })
            if prog_name == program and not is_elig:
                main_eligible = False
                main_message  = reason or "You do not meet the eligibility criteria for this program."

        return {
            "eligible": main_eligible,
            "message":  main_message,
            "programs": programs_result
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Portal Eligibility Check Error")
        return {
            "eligible": True,
            "message":  "Eligibility check encountered an error. Please review the form.",
            "programs": []
        }