import frappe
from frappe.utils.oauth import get_oauth2_authorize_url


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
            frappe.local.flags.redirect_location = redirect_to or "/student-portal"
        raise frappe.Redirect

    context.redirect_to = redirect_to or "/student-portal"
    context.portal_type = "student"

    _load_settings(context)

    context.no_cache = 1
    context.csrf_token = frappe.local.session.data.csrf_token or ""
    context.title = context.portal_title + " — Login"
    context.google_login_url = _get_google_login_url(context.redirect_to)
    context.google_login_error = frappe.local.request.args.get("error", "")


def _get_google_login_url(redirect_to):
    # Returns the URL that starts the Google OAuth flow (redirects to Google's
    # consent screen), or None if Google login isn't configured/enabled — in
    # which case the "Continue with Google" button is hidden on the page.
    if not frappe.db.get_single_value("Student Portal Settings", "enable_google_login"):
        return None
    if not frappe.db.exists(
        "Social Login Key",
        {"social_login_provider": "Google", "enable_social_login": 1}
    ):
        return None
    try:
        # "google" here is the Social Login Key docname, not the display label.
        return get_oauth2_authorize_url("google", redirect_to)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "student/login: google oauth url failed")
        return None


def _load_settings(context):
    try:
        s = frappe.get_single("Student Portal Settings")
        context.primary_color    = s.get("primary_color")   or "#2b2e4a"
        context.secondary_color  = s.get("secondary_color") or "#920c24"
        context.portal_title     = s.get("portal_title")    or "Student Portal"
        context.portal_tagline   = s.get("portal_subtitle") or "Access your courses, results, and attendance"
        context.portal_logo      = frappe.db.get_single_value("Institution Settings", "logo") or ""
    except Exception:
        frappe.log_error(frappe.get_traceback(), "student/login: settings load failed")
        context.primary_color   = "#2b2e4a"
        context.secondary_color = "#920c24"
        context.portal_title    = "Student Portal"
        context.portal_tagline  = "Access your courses, results, and attendance"
        context.portal_logo     = ""
