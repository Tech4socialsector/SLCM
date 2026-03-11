import frappe
from slcm.admission.utils.portal import get_portal_config

no_cache = 1

def get_context(context):
    # ── Portal config + theme ──────────────────────────────────────
    try:
        context.portal_config = get_portal_config()
    except Exception:
        context.portal_config = None

    # ── Get slug from URL ─────────────────────────────────────────
    # Supports both:
    #   /admission/computer-application  (path-based, set by index.py)
    #   /admission/program_detail?slug=computer-application
    slug = frappe.form_dict.get("slug") or ""

    if not slug:
        # Try reading from path: /admission/program_detail/[slug]
        try:
            _path = (getattr(frappe.local, 'path_info', '') or
                     (frappe.request.path if hasattr(frappe, 'request')
                      and frappe.request else ''))
            _parts = [p for p in _path.strip('/').split('/') if p]
            # /admission/program_detail/ba-llb-hons → parts[2]
            if len(_parts) >= 3:
                slug = _parts[2]
            # /admission/ba-llb-hons → parts[1] (if routed via index)
            elif len(_parts) == 2:
                slug = _parts[1]
        except Exception:
            pass

    if not slug:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/admission"
        return

    # ── Fetch Program by slug ─────────────────────────────────────
    prog_name = frappe.db.get_value(
        "Program", {"program_slug": slug}, "name")

    if not prog_name:
        context.program_not_found = True
        context.program = None
        _set_empty_context(context, slug)
        return

    try:
        prog = frappe.get_doc("Program", prog_name)
    except Exception:
        context.program_not_found = True
        context.program = None
        _set_empty_context(context, slug)
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
    context.prog_image       = gf("program_image")
    context.prog_description = gf("description")
    context.prog_intake      = gf("intake_type")
    context.prog_eligibility = gf("eligibility_summary")
    context.prog_app_fee     = gf("application_fee")
    context.prog_deadline    = gf("application_deadline")
    context.prog_brochure    = gf("brochure_url")
    context.prog_slug        = slug
    context.title            = f"{context.prog_name} — Admissions"

    # Media (child table "media" / Program Media)
    try:
        def _normalize_video_url(url):
            """Convert watch URLs to embed URLs."""
            if not url:
                return url
            import re
            # youtu.be/ID
            m = re.search(r'youtu\.be/([^?&]+)', url)
            if m:
                return 'https://www.youtube.com/embed/' + m.group(1)
            # youtube.com/watch?v=ID
            m = re.search(r'youtube\.com/watch\?v=([^&]+)', url)
            if m:
                return 'https://www.youtube.com/embed/' + m.group(1)
            # vimeo.com/ID
            m = re.search(r'vimeo\.com/(\d+)', url)
            if m:
                return 'https://player.vimeo.com/video/' + m.group(1)
            return url

        media_list = []
        for m in (prog.get("media") or []):
            ext_url  = _f(m, "external_url") or ""
            med_url  = _f(m, "media_url") or ""
            mtype    = _f(m, "media_type") or "Image"

            # Auto-detect video from URL if type not set
            if not mtype or mtype == "Image":
                combined = (ext_url + med_url).lower()
                if any(x in combined for x in ["youtube", "youtu.be", "vimeo"]):
                    mtype = "Video"

            # Prefer external_url over media_url; normalize video URLs
            raw_url = ext_url if ext_url else med_url
            if mtype == "Video":
                display_url = _normalize_video_url(raw_url)
            else:
                display_url = raw_url

            media_list.append(frappe._dict({
                "media_type":   mtype,
                "type":         mtype, # alias
                "media_url":    med_url,
                "external_url": ext_url,
                "display_url":  display_url,
                "url":          display_url, # alias
                "caption":      _f(m, "caption") or "",
                "is_hero":      _f(m, "is_hero") or 0,
                "sort_order":   _f(m, "sort_order") or 0,
            }))

        # Sort by sort_order, hero first
        media_list.sort(key=lambda x: (not x.is_hero, x.sort_order))
        context.prog_media  = media_list
        context.prog_images = [m for m in media_list if m.media_type == "Image"]
        context.prog_videos = [m for m in media_list if m.media_type == "Video"]
    except Exception as ex:
        frappe.log_error(str(ex), "prog_detail:media")
        context.prog_media = context.prog_images = context.prog_videos = []

    # ── Curriculum ────────────────────────────────────────────────
    try:
        curriculum = []
        for c in (gf("curriculum_items", []) or []):
            raw_subj = _f(c, "subjects") or ""
            curriculum.append({
                "year_label": _f(c, "year_label") or "",
                "credits":    _f(c, "credits") or "",
                "subjects":   [s.strip() for s in
                               raw_subj.split("\n") if s.strip()],
            })
        context.prog_curriculum = curriculum
    except Exception as ex:
        frappe.log_error(str(ex), "prog_detail:curriculum")
        context.prog_curriculum = []

    # ── Career ────────────────────────────────────────────────────
    try:
        career = []
        for c in (gf("career_items", []) or []):
            career.append({
                "title":       _f(c, "role_title") or "",
                "icon":        _f(c, "icon") or "work",
                "salary":      _f(c, "salary_range") or "",
                "description": _f(c, "description") or "",
            })
        context.prog_career = career
    except Exception as ex:
        frappe.log_error(str(ex), "prog_detail:career")
        context.prog_career = []

    # ── Faculty ───────────────────────────────────────────────────
    try:
        faculty = []
        for f in (gf("faculty_items", []) or []):
            faculty.append({
                "name":           _f(f, "faculty_name") or "",
                "designation":    _f(f, "designation") or "",
                "specialization": _f(f, "specialization") or "",
                "photo":          _f(f, "photo") or "",
                "profile_url":    _f(f, "profile_url") or "",
            })
        context.prog_faculty = faculty
    except Exception as ex:
        frappe.log_error(str(ex), "prog_detail:faculty")
        context.prog_faculty = []

    # ── Eligibility Rules ─────────────────────────────────────────
    try:
        context.eligibility_rules = frappe.get_all(
            "Eligibility Rule",
            filters={"is_active": 1},
            fields=["rule_name", "qualification_level", "rule_type",
                    "required_cgpa", "required_percentage",
                    "description"],
            limit=5
        ) or []
    except Exception:
        context.eligibility_rules = []

    # ── Active cycle ──────────────────────────────────────────────
    from frappe.utils import nowdate
    from slcm.admission.utils.stage_control import can_apply, get_current_stage
    
    active_cycle = frappe.db.get_value(
        "Admission Cycle",
        {"status": "Active"},
        ["name", "cycle_start_date", "cycle_end_date"],
        as_dict=True
    )

    today = nowdate()
    cycle_is_open = False
    if active_cycle:
        cycle_is_open = True
        sd = active_cycle.get("cycle_start_date")
        ed = active_cycle.get("cycle_end_date")
        if sd and str(today) < str(sd):
            cycle_is_open = False
        if ed and str(today) > str(ed):
            cycle_is_open = False

    context.active_cycle = active_cycle
    context.cycle_is_open = cycle_is_open

    # ── can_apply / current stage for this program ──
    if active_cycle and prog:
        intake = prog.get("intake_type") or "CLAT"
        context.can_apply = can_apply(active_cycle.name, intake) if cycle_is_open else False
        stage = get_current_stage(active_cycle.name, intake)
        context.current_stage_name = stage.stage_name if stage else ""

        if not cycle_is_open:
            sd = active_cycle.get("cycle_start_date")
            ed = active_cycle.get("cycle_end_date")
            if sd and str(today) < str(sd):
                context.current_stage_name = "Upcoming"
            elif ed and str(today) > str(ed):
                context.current_stage_name = "Closed"
    else:
        context.can_apply = False
        context.current_stage_name = "Closed"

    # ── Support email ─────────────────────────────────────────────
    try:
        pc = context.portal_config
        context.support_email = (
            (_f(pc, "support_email") if pc else "") or
            "admissions@nlsiu.ac.in"
        )
    except Exception:
        context.support_email = "admissions@nlsiu.ac.in"


def _f(obj, field):
    """Safe field accessor for both dicts and Frappe Document rows."""
    try:
        if hasattr(obj, "get"):
            return obj.get(field)
        return getattr(obj, field, None)
    except Exception:
        return None


def _set_empty_context(context, slug):
    """Set safe empty defaults when program not found."""
    for k in ["prog_name","prog_level","prog_duration","prog_credits",
              "prog_dept","prog_hero","prog_image","prog_description","prog_intake",
              "prog_eligibility","prog_app_fee","prog_deadline",
              "prog_brochure"]:
        setattr(context, k, "")
    context.prog_slug       = slug
    context.prog_media      = []
    context.prog_images     = []
    context.prog_videos     = []
    context.prog_curriculum = []
    context.prog_career     = []
    context.prog_faculty    = []
    context.eligibility_rules = []
    context.active_cycle    = None
    context.support_email   = "admissions@nlsiu.ac.in"
    context.title           = "Program Not Found"
