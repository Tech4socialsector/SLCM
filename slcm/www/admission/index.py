import frappe
from slcm.admission.utils.stage_control import can_apply, get_current_stage

login_required = False

def get_context(context):
    from slcm.admission.utils.portal import get_portal_config

    # ── 1. Portal Config ─────────────────────────────────────────────
    portal_config = get_portal_config()
    context.portal_config = portal_config

    # ── 2. Maintenance mode shortcut ────────────────────────────────
    if not portal_config.get("portal_active", 1):
        context.programs     = []
        context.stats        = {}
        context.announcements = []
        context.active_cycle  = None
        context.app_open      = False
        context.no_cache      = 1
        context.title         = portal_config.get("portal_title", "Admissions")
        return

    # ── 3. Active Admission Cycle ────────────────────────────────────
    active_cycle = frappe.db.get_value(
        "Admission Cycle",
        {"status": "Active"},
        ["name", "application_start", "application_end"],
        as_dict=True
    )

    # ── 4. Is application window open? ───────────────────────────────
    app_open = False
    if active_cycle:
        try:
            from frappe.utils import now_datetime, get_datetime
            now_dt    = now_datetime()
            app_start = get_datetime(active_cycle.application_start) if active_cycle.application_start else None
            app_end   = get_datetime(active_cycle.application_end)   if active_cycle.application_end   else None
            if app_start and app_end:
                app_open = (app_start <= now_dt <= app_end)
            elif not app_start and not app_end:
                # Dates not set — treat as open so admin can test
                app_open = True
        except Exception as e:
            frappe.log_error(title="Portal Index", message=f"app_open calculation failed: {e}")
            app_open = True   # fail open so cards still show Apply Now

    # ── 5. Programs & Announcements ──────────────────────────────────
    try:
        from slcm.admission.utils.portal import (
            get_active_programs, get_active_announcements
        )
        programs      = get_active_programs() or []
        context.announcements = get_active_announcements(limit=6) or []

        # Stage-driven portal control
        active_cycle_name = active_cycle.name if active_cycle else ""
        
        # Check if logged-in user already has an application this cycle
        context.already_applied = False
        context.existing_application = ""
        if frappe.session.user != "Guest" and active_cycle_name:
            existing = frappe.get_all(
                "Applicant",
                filters={
                    "owner": frappe.session.user,
                    "admission_cycle": active_cycle_name
                },
                fields=["name"],
                limit=1
            )
            if existing:
                context.already_applied = True
                context.existing_application = existing[0].name

        for prog in programs:
            # Get intake from Program (single source of truth)
            prog_intake = frappe.db.get_value(
                "Program", prog.get("program") or prog.get("name"), "intake_type"
            ) or "All"
            
            if active_cycle_name:
                prog["can_apply"]          = can_apply(active_cycle_name, prog_intake)
                current_st                 = get_current_stage(active_cycle_name, prog_intake)
                prog["current_stage_name"] = current_st.stage_name if current_st else ""
            else:
                prog["can_apply"]          = False
                prog["current_stage_name"] = "Applications Closed"

        context.programs = programs

    except Exception as e:
        frappe.log_error(title="Portal Index", message=f"fetch failed: {e}")
        context.programs = []
        context.announcements = []

    # ── 6. Stats ─────────────────────────────────────────────────────
    try:
        from slcm.admission.utils.portal import api_get_portal_stats
        context.stats = api_get_portal_stats() or {}
    except Exception:
        context.stats = {}

    context.active_cycle = active_cycle
    context.app_open     = app_open
    context.no_cache     = 1
    context.title        = portal_config.get("portal_title", "Admissions")
