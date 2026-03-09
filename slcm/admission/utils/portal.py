import frappe
import json
from frappe.utils import now, add_days, getdate, today, get_datetime


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
            "social_links": [],
        }

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

        programs = frappe.get_all(
            "Admission Cycle Program",
            filters={"parent": active_cycle, "is_active": 1},
            fields=[
                "program", "program_name", "seats", "eligibility_hint",
                "brochure_url", "program_image", "desciption",
                "program_media", "reservation_policy", "max_applications",
                "application_count", "program_level", "intake_type",
            ],
            order_by="program_name asc"
        )

        import re as _re
        for p in programs:
            p["admission_cycle"] = active_cycle
            # Fetch slug and abbreviation from Program
            prog_info = frappe.db.get_value("Program", p.program, 
                ["program_slug", "program_shortcode", "program_duration"], 
                as_dict=True
            )
            if prog_info:
                p["program_slug"] = prog_info.program_slug or _re.sub(r'[^a-z0-9]+', '-', (p.program or "").lower()).strip('-')
                p["program_abbreviation"] = prog_info.program_shortcode
                p["duration"] = f"{prog_info.program_duration} Years" if prog_info.program_duration else ""
            else:
                p["program_slug"] = _re.sub(r'[^a-z0-9]+', '-', (p.program or "").lower()).strip('-')
                p["program_abbreviation"] = ""
                p["duration"] = ""

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
            total   = int(p.get("max_applications") or p.get("seats") or 0)
            received = int(p.get("application_count") or 0)
            if total > 0:
                pct = min(100, round((received / total) * 100))
                p["fill_pct"] = pct
                if pct >= 90:
                    p["fill_badge"] = f"Only {total - received} seats left"
                    p["fill_class"] = "fill-danger"
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
                p["fill_pct"]   = 0
                p["fill_badge"] = "Open"
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
                "is_active": 1
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
            ["name", "application_end"], as_dict=True
        )
        if not active_cycle: return {}

        total_programs = frappe.db.count("Admission Cycle Program", {"parent": active_cycle.name, "is_active": 1})
        
        # Sum seats from policy if available, else from program row
        total_seats = 0
        cycle_progs = frappe.get_all("Admission Cycle Program", filters={"parent": active_cycle.name, "is_active": 1}, fields=["seats", "reservation_policy"])
        for p in cycle_progs:
            if p.reservation_policy:
                total_seats += frappe.db.get_value("Program Reservation Policy", p.reservation_policy, "total_seats") or 0
            else:
                total_seats += p.seats or 0

        days_left = 0
        if active_cycle.application_end:
            delta = get_datetime(active_cycle.application_end) - get_datetime(now())
            days_left = max(0, delta.days)

        return {
            "total_programs": total_programs,
            "total_seats": total_seats,
            "days_remaining": days_left,
            "apply_by": active_cycle.application_end
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
            filters={"is_active": 1},
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
def api_get_program_media(program_media):
    """Returns media items for a gallery."""
    return frappe.get_all(
        "Media",
        filters={"parent": program_media},
        fields=["media_type", "file", "caption", "sequence"],
        order_by="sequence asc"
    )

def lock_expired_drafts():
    """Scheduler task to lock drafts after cycle deadline."""
    expired_cycles = frappe.get_all(
        "Admission Cycle",
        filters={"application_end": ["<", now()], "status": "Active"},
        fields=["name"]
    )
    for c in expired_cycles:
        frappe.db.sql("""
            UPDATE `tabApplicant` 
            SET application_status = 'Locked' 
            WHERE admission_cycle = %s AND application_status = 'Draft'
        """, c.name)
    frappe.db.commit()
