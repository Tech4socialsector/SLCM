import frappe
import json
from frappe.utils import now, add_days, getdate, today, get_datetime
from slcm.admission.utils.institution import is_multi_campus_enabled

# Admission Cycle.application_form_type — DocType option is "Custom From"; accept "Custom Form" if relabelled.
_CUSTOM_PORTAL_FORM_TYPES = frozenset({"Custom From", "Custom Form"})


def admission_cycle_uses_applicant_web_form(cycle_name: str | None) -> bool:
	"""
	True → Frappe Web Form (/applicant-form/...).
	False when cycle uses the legacy /application_form portal page.
	"""
	if not cycle_name or not frappe.db.exists("Admission Cycle", cycle_name):
		return True
	if not frappe.db.has_column("Admission Cycle", "application_form_type"):
		return True
	ft = (frappe.db.get_value("Admission Cycle", cycle_name, "application_form_type") or "").strip()
	if ft in _CUSTOM_PORTAL_FORM_TYPES:
		return False
	return True


def build_custom_application_form_url(
	program,
	admission_cycle="",
	campus="",
	intake_type="",
	admission_year="",
	academic_year="",
	program_level="",
):
	"""Public URL for the portal application_form page with query-string prefills."""
	from urllib.parse import urlencode

	parts = {
		"program": program or "",
		"admission_cycle": admission_cycle or "",
		"campus": campus or "",
		"intake_type": intake_type or "",
		"admission_year": admission_year or "",
		"academic_year": academic_year or "",
		"program_level": program_level or "",
	}
	q = urlencode({k: v for k, v in parts.items() if v})
	return f"/application_form?{q}" if q else "/application_form"


def build_applicant_form_new_url(
	program,
	admission_cycle="",
	campus="",
	intake_type="",
	admission_year="",
	academic_year="",
	program_level="",
):
	"""New application entry URL: Web Form or custom portal page, based on Admission Cycle."""
	if admission_cycle and not admission_cycle_uses_applicant_web_form(admission_cycle):
		return build_custom_application_form_url(
			program,
			admission_cycle,
			campus=campus,
			intake_type=intake_type,
			admission_year=admission_year,
			academic_year=academic_year,
			program_level=program_level,
		)
	from urllib.parse import urlencode

	parts = {
		"program": program or "",
		"admission_cycle": admission_cycle or "",
		"campus": campus or "",
		"intake_type": intake_type or "",
		"admission_year": admission_year or "",
		"academic_year": academic_year or "",
		"program_level": program_level or "",
	}
	q = urlencode({k: v for k, v in parts.items() if v})
	return f"/applicant-form/new?{q}" if q else "/applicant-form/new"


def build_login_redirect_to_applicant_form_new(
	program,
	admission_cycle="",
	campus="",
	intake_type="",
	admission_year="",
	academic_year="",
	program_level="",
):
	from urllib.parse import quote

	path = build_applicant_form_new_url(
		program,
		admission_cycle,
		campus=campus,
		intake_type=intake_type,
		admission_year=admission_year,
		academic_year=academic_year,
		program_level=program_level,
	)
	return "/login?redirect-to=" + quote(path, safe="/")


def build_existing_applicant_portal_url(
	applicant_name: str,
	admission_cycle: str | None = None,
	*,
	edit: bool = True,
) -> str:
	"""Open an existing Applicant from my-applications or view_application."""
	if not (applicant_name or "").strip():
		return "/my-applications"
	name = applicant_name.strip()
	cycle = (admission_cycle or "").strip()
	if cycle and not admission_cycle_uses_applicant_web_form(cycle):
		from urllib.parse import urlencode

		return f"/application_form?{urlencode({'applicant': name})}"
	if edit:
		return f"/applicant-form/{name}/edit"
	return f"/applicant-form/{name}"


# ── CONFIG ────────────────────────────────────────────────────────
@frappe.whitelist(allow_guest=True)
def api_get_portal_config():
    """Alias for get_portal_config to match JS expectations."""
    return get_portal_config()

@frappe.whitelist(allow_guest=True)
def api_get_announcements(limit=10):
    """Alias for get_active_announcements to match JS expectations."""
    return get_active_announcements(limit=limit)

@frappe.whitelist(allow_guest=True)
def api_get_programs():
    """Alias for get_active_programs to match JS expectations."""
    return get_active_programs()

@frappe.whitelist()
def api_get_my_application():
    """Returns the current user's application for the active cycle."""
    user = frappe.session.user
    if user == "Guest":
        return None
    
    active_cycle = frappe.db.get_value("Admission Cycle", {"status": "Active"}, "name")
    if not active_cycle:
        return None
        
    apps = frappe.get_all(
        "Applicant",
        filters={"owner": user, "admission_cycle": active_cycle},
        fields=["*"],
        limit=1
    )
    return apps[0] if apps else None

@frappe.whitelist(allow_guest=True)
def get_portal_config():
    """
    Returns Applicant Portal Config singleton.
    Falls back to safe defaults if not configured yet.
    """
    try:
        config = frappe.get_single("Applicant Portal Config")
        return {
            "portal_title": config.portal_title or "Admissions",
            "portal_subtitle": config.portal_subtitle or "",
            "hero_image": config.hero_image or "",
            "primary_color": config.primary_color or "#1a3c6e",
            "secondary_color": config.secondary_color or "#c8a14b",
            "slideshow_images": [
                {"image": s.image, "caption": s.caption or "", "idx": s.idx or 0}
                for s in sorted(config.slideshow_images or [], key=lambda x: x.idx or 0)
            ],
            "show_announcement": config.show_announcement,
            "header_announcement": config.header_announcement or "",
            "portal_active": config.portal_active if config.portal_active is not None else 1,
            "maintenance_message": config.maintenance_message or "",
            "program_card_layout": config.program_card_layout or "Grid",
            "show_intake_count": config.show_intake_count,
            "show_eligibility_hint": config.show_eligibility_hint,
            "login_required_for_application": config.login_required_for_application
                if config.login_required_for_application is not None else 1,
            "show_stage_progress": config.show_stage_progress
                if config.show_stage_progress is not None else 1,
            "progress_style": config.progress_style or "Steps",
            "allow_pdf_download": config.allow_pdf_download,
            "contact_email": config.contact_email or "",
            "contact_phone": config.contact_phone or "",
            "footer_text": config.footer_text or "",
            "submission_message": config.submission_message or "",
            "enable_portal_notifications": config.enable_portal_notifications
                if config.enable_portal_notifications is not None else 1,
            "portal_tagline": config.get("portal_tagline") or config.get("portal_subtitle") or "",
            "institution_since": config.get("institution_since") or "",
            "hero_cta_label": config.get("hero_cta_label") or "Explore Programs",
            "hero_cta2_label": config.get("hero_cta2_label") or "Virtual Tour",
            "footer_address": config.get("footer_address") or "",
            "footer_phone": config.get("footer_phone") or "",
            "footer_email": config.get("footer_email") or config.get("contact_email") or "",
            "powerd_by": config.get("powerd_by") or "boscosoft",
            "social_links": [
                {
                    "platform": row.platform,
                    "url": row.url,
                    "is_active": row.is_active
                } for row in (config.social_links or [])
            ],
        }
    except Exception:
        # DocType not yet configured — return safe defaults
        return {
            "portal_title": "Admissions",
            "portal_subtitle": "",
            "hero_image": "",
            "primary_color": "#1a3c6e",
            "secondary_color": "#c8a14b",
            "slideshow_images": [],
            "show_announcement": 0,
            "header_announcement": "",
            "portal_active": 1,
            "maintenance_message": "",
            "program_card_layout": "Grid",
            "show_intake_count": 0,
            "show_eligibility_hint": 0,
            "login_required_for_application": 1,
            "show_stage_progress": 1,
            "progress_style": "Steps",
            "allow_pdf_download": 1,
            "contact_email": "",
            "contact_phone": "",
            "footer_text": "",
            "submission_message": "",
            "enable_portal_notifications": 1,
            "portal_tagline": "",
            "institution_since": "",
            "hero_cta_label": "Explore Programs",
            "hero_cta2_label": "Virtual Tour",
            "footer_address": "",
            "footer_phone": "",
            "footer_email": "",
            "powerd_by": "boscosoft",
            "social_links": [],
        }


def get_portal_website_branding():
    """
    Safe site title + banner for portal Jinja (Website Settings schema varies by Frappe version;
    field "title" no longer exists — use app_name / title_prefix).
    """
    title = ""
    banner = ""
    try:
        if not frappe.db.exists("DocType", "Website Settings"):
            return {"title": title, "banner_image": banner}
        meta = frappe.get_meta("Website Settings")
        for fn in ("app_name", "title_prefix"):
            if meta.has_field(fn):
                v = frappe.db.get_single_value("Website Settings", fn)
                if v and str(v).strip():
                    title = str(v).strip()
                    break
        if meta.has_field("banner_image"):
            banner = frappe.db.get_single_value("Website Settings", "banner_image") or ""
    except Exception:
        pass
    return {"title": title, "banner_image": banner}


def update_website_context(context):
    """
    Globally provides portal_config to all website templates.
    Never raise: a bad/missing Applicant Portal Config must not 500 public pages.
    """
    try:
        context.portal_config = get_portal_config()
        
        # Issue 2: Fetch active programs for the footer
        context.footer_programs = frappe.db.sql("""
            SELECT
                COALESCE(cp.program_name, p.program_name, cp.program) as name,
                COALESCE(p.program_slug, cp.program) as slug
            FROM `tabAdmission Cycle Program` cp
            LEFT JOIN `tabProgram` p ON p.name = cp.program
            WHERE cp.parent = (SELECT name FROM `tabAdmission Cycle` WHERE status = 'Active' LIMIT 1)
            ORDER BY cp.idx ASC, cp.program ASC
            LIMIT 100
        """, as_dict=1) or []
        
    except Exception as e:
        frappe.log_error(
            title="update_website_context failed",
            message=frappe.get_traceback(),
        )
        context.portal_config = {
            "portal_title": "Admissions",
            "portal_active": 1,
            "primary_color": "#1a3c6e",
            "secondary_color": "#c8a14b",
            "social_links": [],
        }
        context.footer_programs = []

@frappe.whitelist(allow_guest=True)
def api_get_hero_slides():
    """
    Returns all slides for the hero banner carousel.
    hero_image is always slide 1.
    slideshow_images child table provides slides 2, 3, 4...
    Returns empty list if neither is set — JS shows text-only hero.
    """
    try:
        config = frappe.get_single("Applicant Portal Config")
        slides = []

        # Slide 1: hero_image (always first if set)
        hero_image = config.get("hero_image")
        if hero_image:
            slides.append({
                "url": hero_image,
                "caption": config.get("portal_title") or "",
                "link_url": ""
            })

        # Slides 2+: slideshow_images child table
        for row in config.get("slideshow_images") or []:
            if row.get("image"):
                slides.append({
                    "url": row.image,
                    "caption": row.get("caption") or "",
                    "link_url": row.get("link_url") or ""
                })

        return slides

    except Exception as e:
        frappe.log_error(f"api_get_hero_slides error: {e}", "Portal API")
        return []

# ── PROGRAMS ──────────────────────────────────────────────────────

@frappe.whitelist()
def api_get_all_program_statuses(cycle):
    """Returns mapping of program name to its current application status."""
    if not cycle or frappe.session.user == "Guest":
        return {}
    
    apps = frappe.get_all(
        "Applicant",
        filters={"owner": frappe.session.user, "admission_cycle": cycle},
        fields=["program", "application_status"]
    )
    
    return {a.program: a.application_status for a in apps}

@frappe.whitelist(allow_guest=True)
def get_active_programs():
    """
    Returns programs listed in the currently active Admission Cycle.
    """
    try:
        active_cycle = frappe.db.get_value("Admission Cycle", {"status": "Active"}, "name")
        if not active_cycle:
            return []

        multi_campus = is_multi_campus_enabled()

        programs = frappe.get_all(
            "Admission Cycle Program",
            filters={"parent": active_cycle, "is_active": 1},
            fields=[
                "program", "program_name", "seats", "eligibility_hint",
                "brochure_url", "program_image", "desciption",
                "program_media", "reservation_policy", "max_applications",
                "application_count", "program_level", "intake_type", "campus",
            ],
            order_by="program_name asc"
        )

        # Live "application_count" should increase based on Applicants submitted
        # in the active cycle for each program.
        # We count Applicant records whose linked Applicant Status is NOT "Closed".
        received_map = {}
        try:
            program_keys = [p.get("program") for p in programs if p.get("program")]
            program_keys = [pk for pk in program_keys if pk]
            if program_keys:
                placeholders = ", ".join(["%s"] * len(program_keys))
                received_rows = frappe.db.sql(
                    f"""
                    SELECT a.program, COUNT(*) AS received
                    FROM `tabApplicant` a
                    LEFT JOIN `tabApplicant Status` s
                        ON s.name = a.application_status
                    WHERE a.admission_cycle = %s
                      AND a.program IN ({placeholders})
                      AND COALESCE(s.status_type, '') != 'Closed'
                    GROUP BY a.program
                    """,
                    [active_cycle] + program_keys,
                    as_dict=True,
                ) or []
                received_map = {
                    r.get("program"): int(r.get("received") or 0)
                    for r in received_rows
                    if r.get("program")
                }
        except Exception:
            # Never break portal rendering due to seat-count issues.
            received_map = {}

        import re as _re
        for p in programs:
            p["admission_cycle"] = active_cycle
            p["multi_campus_enabled"] = 1 if multi_campus else 0
            p["campus_label"] = (p.get("campus") or "").strip()
            if multi_campus and p.get("campus"):
                try:
                    campus_title = (
                        frappe.db.get_value("Campus", p.get("campus"), "campus_name")
                        or p.get("campus")
                    )
                    p["campus_label"] = campus_title
                except Exception:
                    p["campus_label"] = p.get("campus")
            # Fetch slug, abbreviation, and other details from Program
            prog_info = frappe.db.get_value("Program", p.program, 
                ["program_slug", "program_shortcode", "program_duration", "program_image", "program_description", "brochure_file"], 
                as_dict=True
            )
            if prog_info:
                prog_info = frappe._dict(prog_info)
                p["program_slug"] = prog_info.program_slug or _re.sub(r'[^a-z0-9]+', '-', (p.program or "").lower()).strip('-')
                p["program_abbreviation"] = prog_info.program_shortcode
                p["duration"] = f"{prog_info.program_duration} Years" if prog_info.program_duration else ""
                p["program_image"] = prog_info.program_image or p.get("program_image")
                p["program_description"] = prog_info.program_description
                p["brochure_file"] = prog_info.brochure_file
            else:
                p["program_slug"] = _re.sub(r'[^a-z0-9]+', '-', (p.program or "").lower()).strip('-')
                p["program_abbreviation"] = ""
                p["duration"] = ""
                p["program_description"] = ""
                p["brochure_file"] = ""

            p["description"] = p.get("desciption") or ""
            
            raw = p.get("desciption") or ""
            if raw:
                # 20 words plain text for cards
                plain = _re.sub(r'<[^>]+>', '', raw).strip()
                words = plain.split()
                p["desc_short"]    = ' '.join(words[:20])
                p["desc_full"]     = raw
                p["desc_has_more"] = len(words) > 20
            else:
                p["desc_short"]    = p.get("eligibility_hint") or ""
                p["desc_full"]     = ""
                p["desc_has_more"] = False

            # Fill badge
            max_apps = int(p.get("max_applications") or 0)
            received = int(received_map.get(p.get("program")) or 0)
            p["application_count"] = received  # override with live count

            # If max_applications is 0, assume there is no limitation for intake.
            if max_apps > 0:
                total = max_apps
                pct = min(100, round((received / total) * 100)) if total else 0
                p["fill_pct"] = pct
                p["seats_limit"] = total
                p["seats_remaining"] = max(0, total - received)

                p["seats_full"] = received >= total
                p["seats_almost_full"] = (not p["seats_full"]) and pct >= 90

                if p["seats_full"]:
                    p["fill_badge"] = "Seats Full"
                    p["fill_class"] = "fill-danger"
                elif p["seats_almost_full"]:
                    p["fill_badge"] = "Seat Almost Filled"
                    p["fill_class"] = "fill-warning"
                elif pct >= 70:
                    p["fill_badge"] = f"{pct}% filled"
                    p["fill_class"] = "fill-warning"
                elif pct >= 40:
                    p["fill_badge"] = f"{pct}% filled"
                    p["fill_class"] = "fill-info"
                else:
                    p["fill_badge"] = "Seats available"
                    p["fill_class"] = "fill-success"
            else:
                p["fill_pct"] = 0
                p["seats_limit"] = 0
                p["seats_remaining"] = None
                p["seats_full"] = False
                p["seats_almost_full"] = False
                p["fill_badge"] = "Open Intake"
                p["fill_class"] = "fill-success"

        return programs
    except Exception as e:
        frappe.log_error(f"get_active_programs failed: {e}", "Portal")
        return []

def get_active_events(limit=4):
    """Returns announcements of type Event, sorted by event_date."""
    try:
        meta = frappe.get_meta("Portal Announcement")
        fields_available = [f.fieldname for f in meta.fields]
        
        # Base fields we know exist
        fields = ["name", "title", "summary", "announcement_type", "creation"]
        
        # Optional fields
        optional = ["publish_date", "event_date", "event_venue", "featured_image", "created_by_role"]
        for f in optional:
            if f in fields_available:
                fields.append(f)

        return frappe.get_all(
            "Portal Announcement",
            filters={
                "announcement_type": "Event",
                "is_active": 1,
                "status": "Published"
            },
            fields=fields,
            order_by="event_date asc" if "event_date" in fields_available else "creation desc",
            limit=limit
        )
    except Exception as e:
        frappe.log_error(f"get_active_events failed: {e}", "Portal")
        return []

@frappe.whitelist(allow_guest=True)
def api_get_program_images(program, cycle):
    """Returns image gallery for a program in a cycle."""
    res = api_get_program_detail(program, cycle)
    return res.get("images") if res else []

@frappe.whitelist(allow_guest=True)
def api_get_program_detail(program, cycle):
    """Returns full detail for one program including media and categories."""
    try:
        # Get cycle program row
        cp = frappe.db.get_value(
            "Admission Cycle Program",
            {"parent": cycle, "program": program},
            ["program_name", "seats", "eligibility_hint", "brochure_url", "desciption", "program_media", "reservation_policy"],
            as_dict=True
        )
        if not cp: return None

        res = {
            "program": program,
            "program_name": cp.program_name or program,
            "program_abbreviation": frappe.db.get_value("Program", program, "program_shortcode") or "",
            "total_seats": cp.seats or 0,
            "eligibility_hint": cp.eligibility_hint or "",
            "brochure_url": cp.brochure_url or "",
            "description": cp.desciption or "",
            "images": [],
            "videos": [],
            "categories": []
        }

        # Media
        if cp.program_media:
            # brochure_pdf is in Program Media DocType
            brochure_pdf = frappe.db.get_value("Program Media", cp.program_media, "brochure_pdf")
            if brochure_pdf:
                res["brochure_url"] = brochure_pdf

            # media_gallery is the child table fieldname in Program Media
            media_list = frappe.get_all(
                "Media",
                filters={"parent": cp.program_media, "parentfield": "media_gallery"},
                fields=["media_type", "file", "caption", "sequence"],
                order_by="sequence asc"
            )
            for m in media_list:
                if m.media_type == "Image":
                    res["images"].append(m)
                else:
                    res["videos"].append({"video_url": m.file, "caption": m.caption})

        # Categories & Fees from Reservation Policy
        if cp.reservation_policy:
            cats = frappe.get_all(
                "Program Reservation Category",
                filters={"parent": cp.reservation_policy},
                fields=["category_name", "total_seats", "application_fee"],
                order_by="total_seats desc"
            )
            res["categories"] = cats

        return res
    except Exception as e:
        frappe.log_error(f"api_get_program_detail failed: {e}", "Portal")
        return None


# ── STATS & ANNOUNCEMENTS ───────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def api_get_campus_options():
    """Returns list of active campuses."""
    return frappe.get_all("Company", filters={"is_group": 0}, fields=["name", "company_name"])

@frappe.whitelist()
def api_get_application_fee(program, cycle, category=None):
    """Returns the application fee for a program and category."""
    detail = api_get_program_detail(program, cycle)
    if not detail or not detail.get("categories"):
        return 0
    
    if category:
        for cat in detail["categories"]:
            if cat.category_name == category:
                return cat.application_fee or 0
    
    return detail["categories"][0].get("application_fee") or 0

@frappe.whitelist(allow_guest=True)
def api_get_portal_stats():
    """Returns live stats for the admission dashboard."""
    try:
        active_cycle = frappe.db.get_value(
            "Admission Cycle", {"status": "Active"},
            ["name"], as_dict=True
        )
        if not active_cycle: return {}

        active_cycle_name = active_cycle.get("name")
        total_programs = frappe.db.count("Admission Cycle Program", {"parent": active_cycle_name, "is_active": 1})
        
        # Sum seats from policy if available, else from program row
        total_seats = 0
        cycle_progs = frappe.get_all("Admission Cycle Program", filters={"parent": active_cycle_name, "is_active": 1}, fields=["seats", "reservation_policy"])
        for p in cycle_progs:
            if p.reservation_policy:
                total_seats += frappe.db.get_value("Program Reservation Policy", p.reservation_policy, "total_seats") or 0
            else:
                total_seats += p.seats or 0

        return {
            "total_programs": total_programs,
            "total_seats": total_seats,
        }
    except Exception:
        return {}

@frappe.whitelist(allow_guest=True)
def api_get_announcement_detail(ann_name):
    """Returns full detail for one announcement."""
    if not ann_name or not frappe.db.exists("Portal Announcement", ann_name):
        return None
    doc = frappe.get_doc("Portal Announcement", ann_name)
    if not doc.is_active:
        return None
    return doc.as_dict()

@frappe.whitelist(allow_guest=True)
def api_increment_view_count(ann_name):
    """Increments the view count for an announcement."""
    if not ann_name: return
    frappe.db.sql("""
        UPDATE `tabPortal Announcement` 
        SET view_count = view_count + 1 
        WHERE name = %s
    """, ann_name)
    frappe.db.commit()

@frappe.whitelist()
def api_mark_notification_read(notification_id):
    """Alias for web.mark_notifications_read for single ID."""
    from slcm.admission.utils.web import mark_notifications_read
    return mark_notifications_read([notification_id])

@frappe.whitelist(allow_guest=True)
def get_active_announcements(limit=10):
    """Returns active announcements for display on portal"""
    try:
        anns = frappe.get_all("Portal Announcement",
            filters={"is_active": 1, "status": "Published"},
            fields=["name", "title", "announcement_type", "summary",
                    "featured_image", "publish_date", "event_date",
                    "event_venue", "created_by_role", "owner"],
            order_by="publish_date desc",
            limit=limit
        )
        for a in anns:
            # Enrich with owner full name if created_by_role not set
            if not a.get("created_by_role") and a.get("owner"):
                a["created_by_role"] = frappe.db.get_value(
                    "User", a.owner, "full_name"
                ) or a.owner
        return anns
    except Exception as e:
        frappe.log_error(f"get_active_announcements failed: {e}", "Portal")
        return []


# ── UTILS ─────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def api_get_program_media(program_media=None):
    """Returns media items for a gallery, or all media if not specified."""
    if program_media:
        return frappe.get_all(
            "Media",
            filters={"parent": program_media},
            fields=["media_type", "file", "caption", "sequence"],
            order_by="sequence asc"
        )
    
    # Return all media across all programs for applicant_portal compat
    media_list = frappe.db.sql("""
        SELECT 
            m.parent as program_media,
            acp.program,
            m.media_type,
            m.file as image,
            m.file as video_url,
            m.caption,
            m.sequence,
            0 as is_featured
        FROM `tabMedia` m
        JOIN `tabAdmission Cycle Program` acp ON m.parent = acp.program_media
        WHERE acp.is_active = 1
        ORDER BY m.sequence ASC
    """, as_dict=True)
    
    # Also add brochure_pdfs from acp.brochure_url
    brochures = frappe.db.sql("""
        SELECT 
            acp.program,
            'Brochure' as media_type,
            acp.brochure_url as brochure_pdf,
            0 as sequence
        FROM `tabAdmission Cycle Program` acp
        WHERE acp.is_active = 1 AND acp.brochure_url IS NOT NULL AND acp.brochure_url != ''
    """, as_dict=True)
    
    return media_list + brochures

def lock_expired_drafts():
    """Scheduler task to lock drafts after cycle deadline."""
    # This logic needs to be updated to use Stages or Deadlines instead of cycle.application_end
    pass

@frappe.whitelist(allow_guest=True)
def api_get_stage_progress(applicant=None):
    """Stub for applicant_portal.js"""
    return []

@frappe.whitelist(allow_guest=True)
def api_get_campus_status(applicant=None):
    """Stub for applicant_portal.js"""
    return []

def is_application_editable(applicant):
    """
    Returns True if the application is currently editable by the applicant.
    This is determined by the 'is_editable' flag on the current stage
    of the Admission Cycle that matches the application's status.
    """
    if isinstance(applicant, str):
        applicant = frappe.get_doc("Applicant", applicant, ignore_permissions=True)
    
    # If no status, default to True (Draft-like)
    if not applicant.get("application_status"):
        return True
    
    # If no admission_cycle, we can't look up stages
    if not applicant.get("admission_cycle"):
        return True
    
    current_status = applicant.application_status
    
    # Draft is always editable by default, overriding stage settings
    if current_status == "Draft":
        return True
    
    # Fetch stages for this cycle
    stages = frappe.get_all(
        "Admission Cycle Stage",
        filters={
            "parent": applicant.admission_cycle,
            "is_enabled": 1
        },
        fields=["activate_status", "completed_status", "closed_status", "is_editable", "applicable_workflow"],
        order_by="sequence_no asc"
    )
    
    intake = applicant.get("intake_type") or "External Test"
    filtered_stages = [
        s for s in stages
        if s.applicable_workflow == "All" or s.applicable_workflow == intake
    ]
    
    # Look for the stage that matches current status
    for s in filtered_stages:
        if s.activate_status == current_status:
            return bool(s.is_editable)
        if s.completed_status == current_status:
            next_stage_match = any(st.activate_status == current_status for st in filtered_stages)
            if next_stage_match:
                continue
            return bool(s.is_editable)
        
    return False
