import frappe

def get_context(context):
    redirect_to = frappe.local.request.args.get("redirect", "") or \
                  frappe.local.request.args.get("next", "")

    # If user is already logged in, redirect appropriately
    if frappe.session.user != "Guest":
        user_type = frappe.db.get_value("User", frappe.session.user, "user_type") or "Website User"
        if user_type == "System User":
            frappe.local.flags.redirect_location = "/app"
        else:
            frappe.local.flags.redirect_location = redirect_to or "/admission"
        raise frappe.Redirect

    context.redirect_to = redirect_to or "/admission"

    from slcm.admission.utils.portal import get_portal_config
    portal_config = get_portal_config()
    context.portal_config = portal_config

    # Branding
    context.primary_color   = portal_config.get("primary_color")   or "#CB2929"
    context.secondary_color = portal_config.get("secondary_color") or "#8B1A1A"
    context.institution_name = (
        portal_config.get("institution_name") or
        portal_config.get("portal_title") or "NLSIU"
    )
    context.portal_logo    = portal_config.get("logo") or portal_config.get("portal_logo") or ""
    context.support_email  = portal_config.get("support_email") or ""
    context.portal_tagline = portal_config.get("portal_tagline") or "Shaping Tomorrow's Legal Minds"

    # Announcements
    try:
        from slcm.admission.utils.web import get_public_announcements
        context.announcements = get_public_announcements()
    except Exception as e:
        frappe.log_error(title="Portal", message=f"login announcements failed: {e}")
        context.announcements = []

    # Events / Important Dates
    try:
        context.events = frappe.get_all(
            "Portal Announcement",
            filters={"is_active": 1, "announcement_type": "Event", "status": "Published"},
            fields=["title", "summary", "event_date", "featured_image", "event_registration_url"],
            order_by="event_date asc",
            limit=4
        )
        from frappe.utils import format_date
        for ev in context.events:
            if ev.get("event_date"):
                try:
                    ev["date_display"] = format_date(str(ev["event_date"])[:10], "MMM dd")
                except Exception:
                    ev["date_display"] = str(ev["event_date"])[:10]
            else:
                ev["date_display"] = "TBA"
    except Exception:
        context.events = []

    context.no_cache   = 1
    context.csrf_token = frappe.local.session.data.csrf_token or ""
    context.title      = context.institution_name + " — Login"
