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
    context.prog_description = gf("description")
    context.prog_intake      = gf("intake_type")
    context.prog_eligibility = gf("eligibility_summary")
    context.prog_app_fee     = gf("application_fee")
    context.prog_deadline    = gf("application_deadline")
    context.prog_brochure    = gf("brochure_url")
    context.prog_slug        = slug
    context.title            = f"{context.prog_name} — Admissions"

    # ── Media ─────────────────────────────────────────────────────
    try:
        raw = gf("media", [])
        media = []
        for m in (raw if isinstance(raw, list) else []):
            media.append({
                "type":         _f(m, "media_type") or "Image",
                "url":          _f(m, "media_url") or "",
                "external_url": _f(m, "external_url") or "",
                "caption":      _f(m, "caption") or "",
                "sort_order":   int(_f(m, "sort_order") or 0),
            })
        media.sort(key=lambda x: x["sort_order"])
        context.prog_media  = media
        context.prog_images = [m for m in media if m["type"] == "Image"]
        context.prog_videos = [m for m in media if m["type"] == "Video"]
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
    try:
        context.active_cycle = frappe.get_last_doc(
            "Admission Cycle", filters={"status": "Active"})
    except Exception:
        context.active_cycle = None

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
              "prog_dept","prog_hero","prog_description","prog_intake",
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
