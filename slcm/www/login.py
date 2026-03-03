import frappe

def get_context(context):
    # If user is already logged in, redirect appropriately
    if frappe.session.user != "Guest":
        redirect = frappe.local.request.args.get("redirect", "")
        if redirect and redirect.startswith("/app"):
            frappe.local.flags.redirect_location = redirect
        else:
            frappe.local.flags.redirect_location = "/my-applications"
        raise frappe.Redirect

    # Check if this is a desk login attempt (redirect=/app or next=/app)
    redirect_to = frappe.local.request.args.get("redirect", "") or \
                  frappe.local.request.args.get("next", "")
    context.is_desk_redirect = redirect_to.startswith("/app")
    context.redirect_to = redirect_to or "/my-applications"

    from slcm.admission.utils.portal import get_portal_config
    portal_config = get_portal_config()
    context.portal_config = portal_config

    # Announcements for right panel
    try:
        # Field names from JSON: announcement_type, status, publish_date, event_date
        context.announcements = frappe.get_all(
            "Portal Announcement",
            filters={"status": "Published", "announcement_type": "Announcement"},
            fields=["title", "summary as content", "publish_date"],
            order_by="publish_date desc",
            limit=5
        )
    except Exception:
        context.announcements = []

    try:
        context.events = frappe.get_all(
            "Portal Announcement",
            filters={"status": "Published", "announcement_type": "Event"},
            fields=["title", "summary as content", "event_date"],
            order_by="event_date asc",
            limit=5
        )
    except Exception:
        context.events = []

    # Circulars not in type options
    context.circulars = []

    # Capture redirect param
    context.no_cache = 1
    context.title = portal_config.get("portal_title", "Login / Register")
