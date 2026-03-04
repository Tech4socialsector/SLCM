import frappe
import json
from frappe.utils import now, add_days, getdate, today, get_datetime


# ── CONFIG ────────────────────────────────────────────────────────
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
                "brochure_url", "program_image as featured_image", "description",
                "program_media", "reservation_policy"
            ],
            order_by="program_name asc"
        )

        for p in programs:
            p["admission_cycle"] = active_cycle
            p["program_abbreviation"] = frappe.db.get_value("Program", p.program, "program_shortcode") or ""
            # Truncate description for card
            p["has_more_description"] = False
            if p.description and len(p.description) > 160:
                p["short_description"] = p.description[:157] + "..."
                p["has_more_description"] = True
            else:
                p["short_description"] = p.description or ""

        return programs
    except Exception as e:
        frappe.log_error(f"get_active_programs failed: {e}", "Portal")
        return []

@frappe.whitelist(allow_guest=True)
def api_get_program_detail(program, cycle):
    """Returns full detail for one program including media and categories."""
    try:
        # Get cycle program row
        cp = frappe.db.get_value(
            "Admission Cycle Program",
            {"parent": cycle, "program": program},
            ["program_name", "seats", "eligibility_hint", "brochure_url", "description", "program_media", "reservation_policy"],
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
            "description": cp.description or "",
            "images": [],
            "videos": [],
            "categories": []
        }

        # Media
        if cp.program_media:
            media_list = frappe.get_all(
                "Media",
                filters={"parent": cp.program_media},
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
def get_active_announcements(limit=10):
    """Returns published announcements."""
    try:
        return frappe.get_all(
            "Portal Announcement",
            filters={"is_published": 1},
            fields=["title", "content", "announcement_type", "publish_date", "event_date"],
            order_by="publish_date desc",
            limit=limit
        )
    except Exception:
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
