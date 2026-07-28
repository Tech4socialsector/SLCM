from urllib.parse import quote

import frappe
from frappe.utils.oauth import get_oauth2_authorize_url

from slcm.utils.faculty_portal import get_faculty_name


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
        # user_type alone isn't a reliable signal here: it resolves to "System
        # User" for anyone holding ANY desk-access role (e.g. Helpdesk's
        # "Agent"), even if they are also faculty. Check for a linked Faculty
        # record first so a faculty member who happens to also hold a
        # desk-access role still lands on the portal, not /desk.
        if get_faculty_name():
            frappe.local.flags.redirect_location = redirect_to or "/faculty-portal"
        elif user_type == "System User":
            frappe.local.flags.redirect_location = "/desk"
        else:
            # Logged-in Google account has no linked Faculty record — sign them
            # back out and show the error inline on this login page instead of
            # forwarding them to /faculty-portal, which would show a bare,
            # disconnected error page.
            frappe.local.login_manager.logout()
            frappe.db.commit()
            context.not_a_faculty = True

        if not context.get("not_a_faculty"):
            raise frappe.Redirect

    context.redirect_to = redirect_to or "/faculty-portal"
    context.portal_type = "faculty"

    _load_settings(context)

    context.no_cache = 1
    context.csrf_token = frappe.local.session.data.csrf_token or ""
    context.title = context.portal_title + " — Login"
    context.google_login_url = _get_google_login_url(context.redirect_to)
    context.google_login_error = frappe.local.request.args.get("error", "")


def _get_google_login_url(redirect_to):
    # Returns the URL that starts the Google OAuth flow (redirects to Google's
    # consent screen), or None if Google login isn't configured/enabled — in
    # which case the "Sign in with NLS Google account" button is hidden on the page.
    if not frappe.db.get_single_value("Faculty Portal Settings", "enable_google_login"):
        return None
    if not frappe.db.exists(
        "Social Login Key",
        {"social_login_provider": "Google", "enable_social_login": 1}
    ):
        return None
    try:
        # Send the OAuth callback back to this login page (not straight to
        # /faculty-portal) so the has-a-linked-Faculty-record check in
        # get_context() above always runs first. The real destination is
        # carried through as a query param and honored once that check passes.
        callback_target = "/faculty/login?redirect-to=" + quote(redirect_to, safe="")
        # "google" here is the Social Login Key docname, not the display label.
        return get_oauth2_authorize_url("google", callback_target)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "faculty/login: google oauth url failed")
        return None


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
