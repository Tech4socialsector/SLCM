import frappe

def get_context(context):
    # If user is already logged in, redirect appropriately
    if frappe.session.user != "Guest":
        user_type = frappe.db.get_value("User", frappe.session.user, "user_type") or "Website User"
        if user_type == "System User":
            frappe.local.flags.redirect_location = "/desk"
        else:
            frappe.local.flags.redirect_location = "/admission"
        raise frappe.Redirect

    # Check if this is a desk login attempt (redirect=/app or next=/app)
    redirect_to = frappe.local.request.args.get("redirect", "") or \
                  frappe.local.request.args.get("next", "")
    context.is_desk_redirect = redirect_to.startswith("/app")
    context.redirect_to = redirect_to or "/admission"

    from slcm.admission.utils.portal import get_portal_config
    portal_config = get_portal_config()
    context.portal_config = portal_config

    # Announcements for right panel
    try:
        from slcm.admission.utils.web import get_public_announcements
        context.announcements = get_public_announcements()
    except Exception as e:
        frappe.log_error(title="Portal", message=f"login announcements failed: {e}")
        context.announcements = []

    # Important Dates (Events)
    try:
        context.events = frappe.get_all(
            "Portal Announcement",
            filters={"is_active": 1, "announcement_type": "Event"},
            fields=["title", "summary as content", "event_date", "featured_image"],
            order_by="event_date asc",
            limit=5
        )
    except Exception:
        context.events = []

    # Capture redirect param
    context.no_cache = 1
    context.title = portal_config.get("portal_title", "Login / Register")
    context.csrf_token = frappe.local.session.data.csrf_token or ''
