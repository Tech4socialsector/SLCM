import frappe
from frappe import _

login_required = False

def get_context(context):
    from slcm.admission.utils.portal import get_portal_config, api_get_program_detail

    # ── Portal Config ────────────────────────────────────────────────
    portal_config = get_portal_config()
    context.portal_config = portal_config

    # ── Get slug from URL ────────────────────────────────────────────
    # Frappe injects the dynamic segment as frappe.form_dict.name
    # URL: /admission/ba-llb  →  frappe.form_dict.name = "ba-llb"
    slug = frappe.form_dict.get("name") or ""
    if not slug:
        path = frappe.local.request.path  # fallback
        parts = [p for p in path.strip("/").split("/") if p]
        slug = frappe.utils.unquote(parts[-1]) if len(parts) > 1 else ""

    if not slug:
        frappe.throw(_("Program not specified"), frappe.DoesNotExistError)

    # ── Resolve slug → Program name ──────────────────────────────────
    # Try direct name match first (e.g. slug = "LLM" and Program.name = "LLM")
    program_name = None
    if frappe.db.exists("Program", slug):
        program_name = slug
    else:
        # Try matching program_slug custom field
        program_name = frappe.db.get_value(
            "Program", {"program_slug": slug}, "name"
        )

    if not program_name:
        # Try case-insensitive name match
        all_programs = frappe.get_all("Program", fields=["name", "program_slug"])
        for p in all_programs:
            if (p.name or "").lower() == slug.lower():
                program_name = p.name
                break
            if (p.program_slug or "").lower() == slug.lower():
                program_name = p.name
                break

    if not program_name:
        frappe.throw(_(f"Program '{slug}' not found"), frappe.DoesNotExistError)

    # ── Active cycle ─────────────────────────────────────────────────
    active_cycle = frappe.db.get_value(
        "Admission Cycle", {"status": "Active"}, "name"
    )
    if not active_cycle:
        frappe.throw(_("No active admission cycle"), frappe.DoesNotExistError)

    # ── Program detail ───────────────────────────────────────────────
    detail = api_get_program_detail(program_name, active_cycle)
    if not detail:
        # Program exists but not in active cycle — show basic info
        detail = {
            "program": program_name,
            "program_name": frappe.db.get_value("Program", program_name, "program_name") or program_name,
            "program_abbreviation": "",
            "total_seats": 0,
            "eligibility_hint": "",
            "brochure_url": "",
            "description": "",
            "images": [],
            "videos": [],
            "categories": [],
        }

    # ── Application window open? ─────────────────────────────────────
    app_open = False
    try:
        from frappe.utils import now_datetime, get_datetime
        cycle_doc = frappe.get_doc("Admission Cycle", active_cycle)
        if cycle_doc.application_start and cycle_doc.application_end:
            now_dt = now_datetime()
            app_open = (
                get_datetime(cycle_doc.application_start) <= now_dt <=
                get_datetime(cycle_doc.application_end)
            )
        else:
            app_open = True  # no dates set — treat as open
    except Exception:
        app_open = True

    # ── Slug for Apply Now URL ───────────────────────────────────────
    program_slug = frappe.db.get_value("Program", program_name, "program_slug") or slug

    context.program       = detail
    context.program_slug  = program_slug
    context.app_open      = app_open
    context.active_cycle  = active_cycle
    context.no_cache      = 1
    context.title         = detail.get("program_name", "Program Detail")
