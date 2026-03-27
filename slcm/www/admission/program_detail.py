import frappe
from slcm.admission.utils.portal import (
    build_applicant_form_new_url,
    build_login_redirect_to_applicant_form_new,
    get_portal_config,
)

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
    context.prog_description = gf("program_description")
    context.prog_intake      = gf("intake_type")
    context.prog_eligibility = gf("eligibility_summary")
    context.prog_app_fee     = gf("application_fee")
    context.prog_deadline    = gf("application_deadline")
    context.prog_brochure    = gf("brochure_file")
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

    # ── Active cycle ──────────────────────────────────────────────
    try:
        context.active_cycle = frappe.get_last_doc(
            "Admission Cycle", filters={"status": "Active"})
        if context.active_cycle:
            context.admission_cycle = context.active_cycle.name
            context.admission_year = context.active_cycle.admission_year
            context.academic_year = getattr(context.active_cycle, "academic_year", None) or ""
    except Exception:
        context.active_cycle = None
        context.admission_cycle = None
        context.admission_year = None
        context.academic_year = ""

    ac_campus = ""
    ac_intake = ""
    ac_prog_level = (context.prog_level or "").strip()
    if prog_name and context.active_cycle:
        acp = frappe.db.get_value(
            "Admission Cycle Program",
            {"parent": context.active_cycle.name, "program": prog_name, "is_active": 1},
            ["campus", "intake_type", "program_level"],
            as_dict=True,
        )
        if acp:
            ac_campus = (acp.get("campus") or "").strip()
            ac_intake = (acp.get("intake_type") or "").strip()
            if acp.get("program_level"):
                ac_prog_level = (acp.get("program_level") or "").strip()

    _cn = context.active_cycle.name if context.active_cycle else ""
    _ay = (context.admission_year or "") if context.active_cycle else ""
    _aac = (getattr(context, "academic_year", None) or "") if context.active_cycle else ""

    context.apply_web_form_url = build_applicant_form_new_url(
        prog_name or "",
        _cn,
        campus=ac_campus,
        intake_type=ac_intake,
        admission_year=_ay,
        academic_year=_aac,
        program_level=ac_prog_level,
    )
    context.apply_web_form_login_url = build_login_redirect_to_applicant_form_new(
        prog_name or "",
        _cn,
        campus=ac_campus,
        intake_type=ac_intake,
        admission_year=_ay,
        academic_year=_aac,
        program_level=ac_prog_level,
    )

    # ── Eligibility Rules ─────────────────────────────────────────
    try:
        rules = []
        if prog_name and context.active_cycle:
            mappings = frappe.get_all(
                "Eligibility Rule Mapping",
                filters={
                    "program": prog_name,
                    "admission_cycle": context.active_cycle.name,
                    "is_active": 1
                },
                fields=["name"]
            )
            
            for mapping in mappings:
                mapping_doc = frappe.get_doc("Eligibility Rule Mapping", mapping.name)
                for r_row in mapping_doc.rule:
                    rule_doc = frappe.get_doc("Eligibility Rule", r_row.rule)
                    if rule_doc.is_active:
                        rules.append({
                            "rule_name": rule_doc.rule_name,
                            "qualification_level": rule_doc.qualification_level,
                            "rule_type": rule_doc.rule_type,
                            "required_cgpa": rule_doc.required_cgpa,
                            "required_percentage": rule_doc.required_percentage,
                            "description": rule_doc.description
                        })
        context.eligibility_rules = rules
    except Exception as ex:
        frappe.log_error(str(ex), "prog_detail:eligibility_rules")
        context.eligibility_rules = []

    # ── user application status ───────────────────────────────────
    context.user_app_name   = ""
    context.user_app_status = ""
    context.has_any_application = False
    if frappe.session.user and frappe.session.user != "Guest":
        try:
            # Only consider applications in the active cycle
            filters = {"email": frappe.session.user}
            if context.active_cycle:
                filters["admission_cycle"] = context.active_cycle.name

            _all = frappe.get_all(
                "Applicant",
                filters=filters,
                fields=["name", "program", "application_status"],
                order_by="creation desc"
            )
            
            if _all:
                context.has_any_application = True
                # 2. Match for this specific program
                for _a in _all:
                    _p = (_a.get("program") or "").strip().lower()
                    _t = (prog.name or "").strip().lower()
                    _s = (slug or "").strip().lower()
                    if _p == _t or _p == _s:
                        context.user_app_name   = _a.get("name") or ""
                        context.user_app_status = _a.get("application_status") or ""
                        break
        except Exception as _ex:
            frappe.log_error(title="prog_detail_app_lookup", message=str(_ex))

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
    context.admission_cycle = None
    context.admission_year  = None
    context.academic_year   = ""
    context.support_email   = "admissions@nlsiu.ac.in"
    context.title           = "Program Not Found"
    context.apply_web_form_url = "/admission"
    context.apply_web_form_login_url = "/login?redirect-to=/admission"
    context.user_app_name = ""
    context.user_app_status = ""
