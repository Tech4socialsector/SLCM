import frappe


no_cache = 1


def get_context(context):
    redirect_to = (
        frappe.local.request.args.get("redirect-to", "") or
        frappe.local.request.args.get("redirect_to", "") or
        frappe.local.request.args.get("redirect", "") or
        frappe.local.request.args.get("next", "")
    )

    if frappe.session.user != "Guest":
        user_type = frappe.db.get_value("User", frappe.session.user, "user_type") or "Website User"
        if user_type == "System User":
            frappe.local.flags.redirect_location = "/desk"
        else:
            frappe.local.flags.redirect_location = redirect_to or "/faculty-portal"
        raise frappe.Redirect

    context.redirect_to = redirect_to or "/faculty-portal"
    context.portal_type = "faculty"

    _load_settings(context)

    context.no_cache = 1
    context.csrf_token = frappe.local.session.data.csrf_token or ""
    context.title = context.portal_title + " — Login"


def _load_settings(context):
    try:
        s = frappe.get_single("Faculty Portal Settings")
        context.primary_color    = s.get("primary_color")   or "#2b2e4a"
        context.secondary_color  = s.get("secondary_color") or "#920c24"
        context.portal_title     = s.get("portal_title")    or "Faculty Portal"
        context.portal_tagline   = s.get("portal_subtitle") or "Manage your classes, marks, and attendance"
        context.portal_logo      = frappe.db.get_single_value("Institution Settings", "logo") or ""
    except Exception:
        frappe.log_error(frappe.get_traceback(), "faculty/login: settings load failed")
        context.primary_color   = "#2b2e4a"
        context.secondary_color = "#920c24"
        context.portal_title    = "Faculty Portal"
        context.portal_tagline  = "Manage your classes, marks, and attendance"
        context.portal_logo     = ""
