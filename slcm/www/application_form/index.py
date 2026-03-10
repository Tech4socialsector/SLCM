import frappe
from frappe import _
from frappe.utils import flt, now, nowdate

from slcm.utils.phone_utils import sanitize_phone_for_frappe


# ═══════════════════════════════════════════════════════════════════
#  START APPLICATION (from admission listing only — sets session, no URL)
# ═══════════════════════════════════════════════════════════════════

@frappe.whitelist(allow_guest=False)
def start_application(program=None, admission_cycle=None, campus=None, program_level=None, intake_type=None):
    """
    Called when user clicks Apply Now from the admission program listing.
    Sets session so the application form can lock program/cycle/campus.
    Redirects to /application_form (no query params) so user cannot change program via URL.
    """
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/application_form"
        raise frappe.Redirect
    program = (program or "").strip()
    admission_cycle = (admission_cycle or "").strip()
    if not program or not admission_cycle:
        frappe.local.flags.redirect_location = "/admission"
        raise frappe.Redirect
    # Validate that this program+cycle exists in Admission Cycle Program
    exists = frappe.db.exists(
        "Admission Cycle Program",
        {"parent": admission_cycle, "program": program, "is_active": 1}
    )
    if not exists:
        frappe.local.flags.redirect_location = "/admission"
        raise frappe.Redirect
    # Store in session (Frappe session is server-side)
    if not hasattr(frappe.session, "application_form_selection"):
        frappe.session.setdefault("application_form_selection", {})
    sel = frappe.session.get("application_form_selection") or {}
    sel["program"] = program
    sel["admission_cycle"] = admission_cycle
    sel["campus"] = (campus or "").strip() or None
    sel["program_level"] = (program_level or "").strip() or None
    sel["intake_type"] = (intake_type or "").strip() or None
    frappe.session["application_form_selection"] = sel
    frappe.local.flags.redirect_location = "/application_form"
    raise frappe.Redirect


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
        frappe.local.flags.redirect_location = "/login?redirect-to=/application_form"
        raise frappe.Redirect

    context.no_cache = 1
    context.show_sidebar = False

    # ── Pre-fill existing applicant doc (or leave empty for new app) ───
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

    # ── Program / Cycle / Campus: from URL (Apply Now link), then session, then existing draft ──
    # URL params are allowed when coming from admission listing; we validate and store in session so program stays locked.
    session_sel = (frappe.session.get("application_form_selection") or {}) if hasattr(frappe.session, "get") else {}
    app_data = context.applicant_data or {}
    url_program = (frappe.form_dict.get("program") or "").strip()
    url_cycle = (frappe.form_dict.get("admission_cycle") or "").strip()
    url_valid = False
    if url_program and url_cycle:
        exists = frappe.db.exists(
            "Admission Cycle Program",
            {"parent": url_cycle, "program": url_program, "is_active": 1},
        )
        if exists:
            url_valid = True
            sel = dict(session_sel)
            sel["program"] = url_program
            sel["admission_cycle"] = url_cycle
            sel["campus"] = (frappe.form_dict.get("campus") or "").strip() or None
            sel["program_level"] = (frappe.form_dict.get("program_level") or "").strip() or None
            sel["intake_type"] = (frappe.form_dict.get("intake_type") or "").strip() or None
            frappe.session["application_form_selection"] = sel
            session_sel = sel

    if app_data.get("name") and app_data.get("docstatus") == 0:
        context.prefill_program = app_data.get("program") or session_sel.get("program") or ""
        context.prefill_admission_cycle = app_data.get("admission_cycle") or session_sel.get("admission_cycle") or ""
        context.prefill_campus = app_data.get("campus") or session_sel.get("campus") or ""
        context.prefill_program_level = app_data.get("program_level") or session_sel.get("program_level") or ""
        context.prefill_intake_type = app_data.get("intake_type") or session_sel.get("intake_type") or ""
        context.prefill_academic_year = app_data.get("academic_year") or ""
    else:
        context.prefill_program = session_sel.get("program") or ""
        context.prefill_admission_cycle = session_sel.get("admission_cycle") or ""
        context.prefill_campus = session_sel.get("campus") or ""
        context.prefill_program_level = session_sel.get("program_level") or ""
        context.prefill_intake_type = session_sel.get("intake_type") or ""
        context.prefill_academic_year = ""

    if not context.prefill_program or not context.prefill_admission_cycle:
        frappe.local.flags.redirect_location = "/admission"
        raise frappe.Redirect

    context.program_readonly = True  # Always lock: user must select from listing

    # ── Academic year from Admission Cycle (before seeding so applicant_data gets it) ──
    if context.prefill_admission_cycle and not context.prefill_academic_year:
        try:
            context.prefill_academic_year = frappe.db.get_value(
                "Admission Cycle", context.prefill_admission_cycle, "academic_year"
            ) or ""
        except Exception:
            context.prefill_academic_year = ""

    # When no existing draft, seed applicant_data with locked values so form has them
    if not context.applicant_data or not context.applicant_data.get("name"):
        context.applicant_data = dict(context.applicant_data or {})
        context.applicant_data.setdefault("program", context.prefill_program)
        context.applicant_data.setdefault("admission_cycle", context.prefill_admission_cycle)
        context.applicant_data.setdefault("campus", context.prefill_campus or "")
        context.applicant_data.setdefault("program_level", context.prefill_program_level or "")
        context.applicant_data.setdefault("academic_year", context.prefill_academic_year or "")
        context.applicant_data.setdefault("application_type", context.prefill_intake_type or "")

    # ── Programs (for hidden/display only; selection is locked) ─────────
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

    # ── Campuses: from Admission Cycle Program (this cycle + program only) ──
    try:
        acp_rows = frappe.get_all(
            "Admission Cycle Program",
            filters={
                "parent": context.prefill_admission_cycle,
                "program": context.prefill_program,
                "is_active": 1,
            },
            fields=["campus"],
            order_by="idx asc"
        )
        campus_ids = [r.get("campus") for r in (acp_rows or []) if r.get("campus")]
        if campus_ids:
            context.campuses = frappe.get_all(
                "Campus",
                fields=["name", "campus_name"],
                filters={"name": ["in", campus_ids], "is_active": 1},
                order_by="campus_name asc"
            ) or []
        else:
            # No campus in ACP: allow all active campuses for backward compatibility
            context.campuses = frappe.get_all(
                "Campus",
                fields=["name", "campus_name"],
                filters={"is_active": 1},
                order_by="campus_name asc"
            ) or []
    except Exception:
        context.campuses = []

    # ── Entrance Test Providers (for Test Centre preference dropdowns) ──
    try:
        context.entrance_test_providers = frappe.get_all(
            "Entrance Test Provider",
            fields=["name", "provider_name"],
            filters={"active": 1},
            order_by="provider_name asc"
        )
    except Exception:
        context.entrance_test_providers = []

    # ── Academic Years; ensure prefill year is in list ──────────────────
    try:
        context.academic_years = frappe.get_all(
            "Academic Year",
            fields=["name"],
            order_by="name desc"
        ) or []
        if context.prefill_academic_year and not any(
            (y.get("name") or y.name) == context.prefill_academic_year
            for y in context.academic_years
        ):
            context.academic_years = [{"name": context.prefill_academic_year}] + list(context.academic_years)
    except Exception:
        context.academic_years = []

    # ── Admission Cycles (active only); ensure prefill cycle is in list ─
    try:
        context.admission_cycles = frappe.get_all(
            "Admission Cycle",
            fields=["name"],
            filters={"status": "Active"},
            order_by="name desc"
        ) or []
        if context.prefill_admission_cycle and not any(
            (c.get("name") or c.name) == context.prefill_admission_cycle
            for c in context.admission_cycles
        ):
            context.admission_cycles = [{"name": context.prefill_admission_cycle}] + list(context.admission_cycles)
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

    # ── States (from State doctype) ─────────────────────────────────────
    try:
        context.states = frappe.get_all(
            "State",
            fields=["name"],
            order_by="name asc"
        )
    except Exception:
        context.states = []

    # ── Cities (static list; no City doctype — extend as needed) ────────
    context.cities = get_common_cities()

    # ── Form config: admission cycle → entrance test / program levels ───
    # Used to show/hide sections by program (e.g. PhD section only for Research Course)
    context.form_config = get_form_config_for_cycles()

    return context


def get_common_cities():
    """Return a list of common city names for the City select. Override or extend via DocType if needed."""
    return [
        "Bengaluru", "Mumbai", "Delhi", "Chennai", "Kolkata", "Hyderabad", "Pune", "Ahmedabad",
        "Jaipur", "Lucknow", "Kanpur", "Nagpur", "Indore", "Thane", "Bhopal", "Visakhapatnam",
        "Patna", "Vadodara", "Ghaziabad", "Ludhiana", "Agra", "Nashik", "Faridabad", "Meerut",
        "Rajkot", "Varanasi", "Srinagar", "Aurangabad", "Dhanbad", "Amritsar", "Allahabad",
        "Ranchi", "Howrah", "Coimbatore", "Jabalpur", "Gwalior", "Vijayawada", "Jodhpur",
        "Madurai", "Raipur", "Kota", "Chandigarh", "Guwahati", "Solapur", "Tiruchirappalli",
        "Bareilly", "Mysore", "Tirunelveli", "Gurgaon", "Aligarh", "Bhubaneswar", "Salem",
        "Warangal", "Mira-Bhayandar", "Thiruvananthapuram", "Bhiwandi", "Saharanpur",
        "Other",
    ]


def get_form_config_for_cycles():
    """
    Returns a dict keyed by admission_cycle name: which program_levels and
    intake_types exist in that cycle (from Admission Cycle Program + Program).
    Enables the form to show fields relevant to the selected program/entrance test.
    """
    out = {}
    try:
        cycles = frappe.get_all(
            "Admission Cycle",
            fields=["name"],
            filters={"status": "Active"},
            order_by="name desc"
        )
        for c in cycles or []:
            cycle_name = c.name
            programs = frappe.get_all(
                "Admission Cycle Program",
                filters={"parent": cycle_name},
                fields=["program", "program_level", "intake_type"]
            )
            if not programs:
                # Fallback: get program_level from Program link
                programs = frappe.db.sql("""
                    SELECT acp.program, p.program_level, acp.intake_type
                    FROM `tabAdmission Cycle Program` acp
                    LEFT JOIN `tabProgram` p ON p.name = acp.program
                    WHERE acp.parent = %s
                """, (cycle_name,), as_dict=True)
            levels = set()
            intake_types = set()
            for row in programs or []:
                prog = row.get("program") if isinstance(row, dict) else getattr(row, "program", None)
                pl = (row.get("program_level") if isinstance(row, dict) else getattr(row, "program_level", None)) or (frappe.db.get_value("Program", prog, "program_level") if prog else None)
                it = row.get("intake_type") if isinstance(row, dict) else getattr(row, "intake_type", None)
                if pl:
                    levels.add(pl)
                if it:
                    intake_types.add(it)
            out[cycle_name] = {
                "program_levels": list(levels),
                "intake_types": list(intake_types),
            }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Application Form — form_config")
    return out


# ═══════════════════════════════════════════════════════════════════
#  SAVE / SUBMIT API
# ═══════════════════════════════════════════════════════════════════

@frappe.whitelist()
def save_form(data):
    """
    Save (draft) or submit (final) an Applicant document.

    KEY FIX NOTES
    ─────────────
    - Never use frappe.local.response.http_status_code + return to signal errors.
      frappe.call() on the JS side treats any non-200 as a thrown exception, and the
      error message ends up inside e.responseJSON._server_messages (a JSON-encoded
      string), NOT e.responseJSON.message. This is what caused the generic
      "Submission failed" message.
    - Instead we always return a plain dict with a top-level "error" key for failures
      and a "name" key for successes. The JS checks these keys on res.message.
    - doc.submit() must also use ignore_permissions=True; without it, the Applicant
      role raises a PermissionError that was being silently swallowed.
    - frappe.parse_json() safely handles both str and dict inputs.
    """
    # Frappe may pass data as a JSON string or already-parsed dict
    if isinstance(data, str):
        data = frappe.parse_json(data)
    if not isinstance(data, dict):
        return {"error": "Invalid data format."}

    user = frappe.session.user
    if user == "Guest":
        return {"error": _("You must be logged in to save an application.")}

    email = frappe.db.get_value("User", user, "email") or user
    is_submit = bool(data.get("__submit"))

    # ── Get valid fields from DocType meta ───────────────────────────
    try:
        meta = frappe.get_meta("Applicant")
    except Exception:
        return {"error": _("Applicant DocType not found. Please contact the administrator.")}

    SKIP_TYPES = {"Table", "Section Break", "Column Break", "Tab Break", "HTML", "Button"}
    valid_scalar_fields = {f.fieldname for f in meta.fields if f.fieldtype not in SKIP_TYPES}
    child_table_fields  = {"ug_degree_details", "pg_degree_details", "categories"}

    # ── Sanitise — only accept known fields ──────────────────────────
    sanitized = {}
    for key, value in data.items():
        if key.startswith("__"):
            continue
        if key in valid_scalar_fields or key in child_table_fields:
            sanitized[key] = value

    # ── Build and sanitize phone fields (E.164 for Frappe Phone fieldtype) ─
    PHONE_FIELDS = ("mobile_number", "alternate_contact", "father_mobile", "mother_mobile", "guardian_mobile")
    for field in PHONE_FIELDS:
        if field not in valid_scalar_fields:
            continue
        combined = sanitized.get(field)
        cc_key = field + "_cc"
        num_key = field + "_num"
        if not combined and (cc_key in data or num_key in data):
            cc = (data.get(cc_key) or "+91")
            if isinstance(cc, str) and not cc.startswith("+"):
                cc = "+" + cc
            num = (data.get(num_key) or "")
            if isinstance(num, str):
                num = "".join(c for c in num if c.isdigit())
            combined = (cc or "+91") + num
        sanitized[field] = sanitize_phone_for_frappe(combined)

    # ── Find or create Applicant doc ─────────────────────────────────
    try:
        existing_name = frappe.db.get_value("Applicant", {"email": email}, "name")
    except Exception:
        existing_name = None

    try:
        if existing_name:
            doc = frappe.get_doc("Applicant", existing_name)
        else:
            doc = frappe.new_doc("Applicant")
            doc.email = email
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "save_form — get/new doc")
        return {"error": _("Could not load application record: {0}").format(str(e))}

    # ── Apply scalar fields ──────────────────────────────────────────
    scalar_data = {k: v for k, v in sanitized.items() if k not in child_table_fields}
    try:
        doc.update(scalar_data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "save_form — doc.update")
        return {"error": _("Error setting fields: {0}").format(str(e))}

    # ── Apply child tables ───────────────────────────────────────────
    # Strip internal Frappe row-keys so append() doesn't try to match existing rows
    _INTERNAL_KEYS = {"name", "idx", "doctype", "parent", "parentfield", "parenttype",
                      "owner", "creation", "modified", "modified_by", "docstatus"}

    for ct_field in child_table_fields:
        if ct_field in sanitized:
            doc.set(ct_field, [])
            rows = sanitized[ct_field]
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        clean_row = {
                            k: v for k, v in row.items()
                            if k not in _INTERNAL_KEYS and not k.startswith("__")
                        }
                        try:
                            doc.append(ct_field, clean_row)
                        except Exception:
                            pass  # Skip malformed rows silently

    # Always stamp the authenticated email — do not trust form input
    doc.email = email

    # ── Save or Submit ───────────────────────────────────────────────
    try:
        doc.flags.ignore_permissions = True

        if is_submit:
            # Save first so we have a persistent record, then submit
            if not doc.name or doc.is_new():
                doc.insert(ignore_permissions=True)
            else:
                doc.save(ignore_permissions=True)

            frappe.db.commit()   # commit the save before submitting

            doc.flags.ignore_permissions = True
            doc.submit()
            frappe.db.commit()

            # Resolve program and campus for success page display (name, not ID)
            program_name = ""
            campus_name = ""
            if getattr(doc, "program", None):
                program_name = frappe.db.get_value("Program", doc.program, "program_name") or doc.program or ""
            if getattr(doc, "campus", None):
                campus_name = frappe.db.get_value("Campus", doc.campus, "campus_name") or doc.campus or ""

            return {
                "status": "success",
                "name": doc.name,
                "message": _("Application submitted successfully."),
                "docstatus": doc.docstatus,
                "application_status": getattr(doc, "application_status", None),
                "program_name": program_name,
                "campus_name": campus_name,
            }
        else:
            doc.application_status = "Draft"
            if doc.is_new():
                doc.insert(ignore_permissions=True)
            else:
                doc.save(ignore_permissions=True)

            frappe.db.commit()

            return {
                "status": "draft",
                "name": doc.name,
                "message": _("Draft saved."),
                "docstatus": doc.docstatus,
                "application_status": doc.application_status,
            }

    except frappe.ValidationError as e:
        frappe.db.rollback()
        # Return the validation message directly — JS will display it to user
        return {"error": str(e)}

    except frappe.MandatoryError as e:
        frappe.db.rollback()
        return {"error": _("Required fields missing: {0}").format(str(e))}

    except frappe.DuplicateEntryError as e:
        frappe.db.rollback()
        return {"error": _("A duplicate entry was found: {0}").format(str(e))}

    except frappe.PermissionError:
        frappe.db.rollback()
        return {"error": _("You do not have permission to submit this application.")}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Application Form — save_form")
        # Return the raw exception message so we can see it during development.
        # In production you'd replace str(e) with a generic message.
        return {"error": _("Submission error: {0}").format(str(e))}


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