import frappe

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
            frappe.log_error(f"app_open calculation failed: {e}", "Portal Index")
            app_open = True   # fail open so cards still show Apply Now

    # ── 5. Programs ──────────────────────────────────────────────────
    programs = []
    try:
        from slcm.admission.utils.portal import get_active_programs
        programs = get_active_programs() or []
    except Exception as e:
        frappe.log_error(f"get_active_programs failed: {e}", "Portal Index")

    for p in programs:
        p["is_open"]         = app_open
        p["show_filling_fast"] = False
        p["show_closed"]     = not app_open
        p["total_seats"]     = 0
        p["available_seats"] = 0

        rp_name = p.get("reservation_policy")
        if rp_name:
            try:
                rp = frappe.get_doc("Program Reservation Policy", rp_name)
                total     = rp.total_seats or 0
                available = getattr(rp, "total_available", total) or total
                p["total_seats"]     = total
                p["available_seats"] = available
                if total > 0:
                    fill_pct = ((total - available) / total) * 100
                    p["show_filling_fast"] = app_open and fill_pct >= 90
                    p["show_closed"]       = available == 0
            except Exception:
                pass

        # Get URL slug for this program
        p["program_slug"] = frappe.db.get_value(
            "Program", p.get("program"), "program_slug"
        ) or (p.get("program") or "").lower().replace(" ", "-")

    # ── 6. Stats ─────────────────────────────────────────────────────
    try:
        from slcm.admission.utils.portal import api_get_portal_stats
        context.stats = api_get_portal_stats() or {}
    except Exception:
        context.stats = {}

    # ── 7. Announcements ─────────────────────────────────────────────
    try:
        from slcm.admission.utils.portal import get_active_announcements
        context.announcements = get_active_announcements(limit=5) or []
    except Exception:
        context.announcements = []

    context.programs     = programs
    context.active_cycle = active_cycle
    context.app_open     = app_open
    context.no_cache     = 1
    context.title        = portal_config.get("portal_title", "Admissions")
