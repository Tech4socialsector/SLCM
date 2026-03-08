import frappe
from slcm.admission.utils.stage_control import can_apply, get_current_stage

login_required = False

def _load_program_detail(context, slug):
    """Populate context for /admission/[slug] detail view."""
    import frappe
    try:
        from slcm.admission.utils.portal import get_portal_config
        context.portal_config = get_portal_config()
    except Exception:
        context.portal_config = None

    prog_name = frappe.db.get_value(
        "Program", {"program_slug": slug}, "name")

    if not prog_name:
        context.program_not_found = True
        context.program = None
        _set_empty_pd_context(context, slug)
        return

    try:
        prog = frappe.get_doc("Program", prog_name)
    except Exception:
        context.program_not_found = True
        context.program = None
        _set_empty_pd_context(context, slug)
        return

    context.program = prog
    context.program_not_found = False

    def gf(field, default=""):
        try:
            return prog.get(field) or default
        except Exception:
            return default

    context.prog_name        = gf("program_name")
    context.prog_level       = gf("program_level")
    context.prog_duration    = gf("program_duration")
    context.prog_credits     = gf("graduation_credits")
    context.prog_dept        = gf("department")
    context.prog_hero        = gf("hero_image")
    context.prog_image       = gf("program_image")   # NEW: program_image field
    context.prog_description = gf("description")
    context.prog_intake      = gf("intake_type")
    context.prog_eligibility = gf("eligibility_summary")
    context.prog_app_fee     = gf("application_fee")
    context.prog_deadline    = gf("application_deadline")
    context.prog_brochure    = gf("brochure_url")
    context.prog_slug        = slug

    # Media (child table "media" / Program Media)
    try:
        raw = gf("media", []) or []
        media = []
        import re
        for m in (raw if isinstance(raw, list) else []):
            mtype  = _pf(m, "media_type") or "Image"
            murl   = _pf(m, "media_url") or ""
            exturl = _pf(m, "external_url") or ""

            # Determine the single "best URL" for display / iframe
            # Prefer external_url if set, otherwise media_url
            display_url = exturl if exturl else murl

            # Detect if this is a video embed URL
            is_video_url = any(x in display_url.lower() for x in
                               ["youtube.com", "youtu.be", "vimeo.com",
                                "youtube-nocookie.com"])

            # Force type to Video if URL looks like video
            if is_video_url:
                mtype = "Video"

            # Normalize YouTube URLs to embed format
            if "youtu.be/" in display_url:
                vid_id = display_url.split("youtu.be/")[-1].split("?")[0]
                display_url = f"https://www.youtube.com/embed/{vid_id}"
            elif "youtube.com/watch" in display_url:
                vid_id_match = re.search(r"v=([^&]+)", display_url)
                if vid_id_match:
                    display_url = f"https://www.youtube.com/embed/{vid_id_match.group(1)}"
            elif "vimeo.com/" in display_url and "/video/" not in display_url:
                vid_id = display_url.rstrip("/").split("/")[-1]
                display_url = f"https://player.vimeo.com/video/{vid_id}"

            media.append({
                "type":        mtype,
                "url":         display_url,   # normalized URL
                "caption":     _pf(m, "caption") or "",
                "sort_order":  int(_pf(m, "sort_order") or 0),
                "thumb":       murl if mtype == "Image" else "",
            })
        media.sort(key=lambda x: x["sort_order"])
        context.prog_media  = media
        context.prog_images = [m for m in media if m["type"] == "Image"]
        context.prog_videos = [m for m in media if m["type"] == "Video"]
    except Exception as ex:
        frappe.log_error(str(ex), "prog_detail:media")
        context.prog_media = context.prog_images = context.prog_videos = []

    # Curriculum
    try:
        curriculum = []
        for c in (gf("curriculum_items",[]) or []):
            raw_s = _pf(c,"subjects") or ""
            curriculum.append({
                "year_label": _pf(c,"year_label") or "",
                "credits":    _pf(c,"credits") or "",
                "subjects":   [s.strip() for s in raw_s.split("\n") if s.strip()],
            })
        context.prog_curriculum = curriculum
    except Exception as ex:
        frappe.log_error(str(ex),"prog_detail:curriculum")
        context.prog_curriculum = []

    # Career
    try:
        career = []
        for c in (gf("career_items",[]) or []):
            career.append({
                "title":       _pf(c,"role_title") or "",
                "icon":        _pf(c,"icon") or "work",
                "salary":      _pf(c,"salary_range") or "",
                "description": _pf(c,"description") or "",
            })
        context.prog_career = career
    except Exception as ex:
        frappe.log_error(str(ex),"prog_detail:career")
        context.prog_career = []

    # Faculty
    try:
        faculty = []
        for f in (gf("faculty_items",[]) or []):
            faculty.append({
                "name":           _pf(f,"faculty_name") or "",
                "designation":    _pf(f,"designation") or "",
                "specialization": _pf(f,"specialization") or "",
                "photo":          _pf(f,"photo") or "",
                "profile_url":    _pf(f,"profile_url") or "",
            })
        context.prog_faculty = faculty
    except Exception as ex:
        frappe.log_error(str(ex),"prog_detail:faculty")
        context.prog_faculty = []

    # Eligibility Rules
    try:
        context.eligibility_rules = frappe.get_all(
            "Eligibility Rule",
            filters={"is_active": 1},
            fields=["rule_name","qualification_level","rule_type",
                    "required_cgpa","required_percentage","description"],
            limit=5
        ) or []
    except Exception:
        context.eligibility_rules = []

    # Active cycle
    try:
        context.active_cycle = frappe.get_last_doc(
            "Admission Cycle", filters={"status": "Active"})
    except Exception:
        context.active_cycle = None

    # Support email
    try:
        pc = context.portal_config
        context.support_email = (
            (_pf(pc,"support_email") if pc else "") or
            "admissions@nlsiu.ac.in"
        )
    except Exception:
        context.support_email = "admissions@nlsiu.ac.in"


def _pf(obj, field):
    """Safe field accessor for both dicts and Frappe Document rows."""
    try:
        if hasattr(obj, "get"):
            return obj.get(field)
        return getattr(obj, field, None)
    except Exception:
        return None


def _set_empty_pd_context(context, slug):
    for k in ["prog_name","prog_level","prog_duration","prog_credits",
              "prog_dept","prog_hero","prog_image","prog_description","prog_intake",
              "prog_eligibility","prog_app_fee","prog_deadline","prog_brochure"]:
        setattr(context, k, "")
    context.prog_slug        = slug
    context.prog_media       = []
    context.prog_images      = []
    context.prog_videos      = []
    context.prog_curriculum  = []
    context.prog_career      = []
    context.prog_faculty     = []
    context.eligibility_rules = []
    context.active_cycle     = None
    context.support_email    = "admissions@nlsiu.ac.in"

def get_context(context):
    # ── Route detection: /admission vs /admission/[slug] ─────────────
    _slug = ""
    try:
        _path = (
            getattr(frappe.local, "path_info", "") or
            (frappe.request.path
             if hasattr(frappe, "request") and frappe.request else "")
        )
        _parts = [p for p in _path.strip("/").split("/") if p]
        # /admission/ba-llb-hons → ['admission', 'ba-llb-hons']
        if len(_parts) == 2 and _parts[0] == "admission":
            _slug = _parts[1]
    except Exception:
        _slug = ""

    if _slug:
        _load_program_detail(context, _slug)
        context.show_detail = True
        context.title = (context.prog_name or "Program") + " — Admissions"
        return   # ← exit early, index.html renders detail view

    context.show_detail = False

    from slcm.admission.utils.portal import get_portal_config

    # ── 1. Portal Config ─────────────────────────────────────────────
    portal_config = get_portal_config()
    context.portal_config = portal_config

    # Social media links from Portal Social Link child table
    try:
        context.social_links = [
            row for row in (portal_config.get("social_links") or [])
            if (row.get("is_active") if hasattr(row, 'get') else getattr(row, 'is_active', 1))
        ] if portal_config else []
    except Exception:
        context.social_links = []

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
            get_active_programs, get_active_announcements, get_active_events
        )
        programs      = get_active_programs() or []
        context.announcements = get_active_announcements(limit=10) or []
        context.events = get_active_events(limit=4) or []

        # Split announcements into non-event ones only
        context.announcements = [
            a for a in (context.announcements or [])
            if (a.get("announcement_type") or "") != "Event"
        ]

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
        context.events = []

    # ── 6. Stats ─────────────────────────────────────────────────────
    try:
        from slcm.admission.utils.portal import api_get_portal_stats
        context.stats = api_get_portal_stats() or {}
    except Exception:
        context.stats = {}

    # Fallback: compute basic stats from what we already have
    if not context.stats or not context.stats.get('total_programs'):
        try:
            from frappe.utils import date_diff, today as get_today, getdate
            _today = get_today()
            _app_end = active_cycle.application_end if active_cycle else None
            _days = None
            if _app_end:
                try:
                    _days = date_diff(_app_end, _today)
                    if _days < 0: _days = 0
                except Exception:
                    _days = None
            context.stats = {
                'total_programs': len(context.programs or []),
                'total_seats': sum(
                    int(p.get('seats') or p.get('total_seats') or 0)
                    for p in (context.programs or [])
                ) or None,
                'days_remaining': _days,
                'apply_by': _app_end,
            }
        except Exception:
            context.stats = {'total_programs': len(context.programs or [])}

    context.active_cycle = active_cycle
    context.app_open     = app_open
    context.no_cache     = 1
    context.title        = portal_config.get("portal_title", "Admissions")

    # ── 7. New Portal Config Fields ──────────────────────────────────
    context.portal_tagline    = portal_config.get("portal_tagline") or portal_config.get("portal_subtitle") or ""
    context.institution_since = portal_config.get("institution_since") or ""
    context.hero_cta_label    = portal_config.get("hero_cta_label") or "Explore Programs"
    context.hero_cta2_label   = portal_config.get("hero_cta2_label") or "Virtual Tour"
    context.footer_address    = portal_config.get("footer_address") or ""
    context.footer_phone      = portal_config.get("footer_phone") or ""
    context.footer_email      = portal_config.get("footer_email") or portal_config.get("contact_email") or ""
    context.social_links      = portal_config.get("social_links") or []
