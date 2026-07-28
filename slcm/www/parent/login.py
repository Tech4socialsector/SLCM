from urllib.parse import quote

import frappe
from frappe.utils.oauth import get_oauth2_authorize_url

from slcm.slcm.utils.parent_portal import get_parent_wards


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
        # Check for at least one linked ward (Student Parent row) before
        # trusting user_type — a parent who also holds some desk-access role
        # should still land on the portal, not /desk.
        if get_parent_wards(frappe.session.user):
            frappe.local.flags.redirect_location = redirect_to or "/parent-portal"
        elif user_type == "System User":
            frappe.local.flags.redirect_location = "/desk"
        else:
            # Logged-in Google account has no linked ward — sign them back
            # out and show the error inline on this login page instead of
            # forwarding them to /parent-portal, which would show a bare,
            # disconnected error page.
            frappe.local.login_manager.logout()
            frappe.db.commit()
            context.not_a_parent = True

        if not context.get("not_a_parent"):
            raise frappe.Redirect

    context.redirect_to = redirect_to or "/parent-portal"
    context.portal_type = "parent"

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
    if not frappe.db.get_single_value("Parent Portal Settings", "enable_google_login"):
        return None
    if not frappe.db.exists(
        "Social Login Key",
        {"social_login_provider": "Google", "enable_social_login": 1}
    ):
        return None
    try:
        # Send the OAuth callback back to this login page (not straight to
        # /parent-portal) so the has-a-linked-ward check in get_context()
        # above always runs first. The real destination is carried through
        # as a query param and honored once that check passes.
        callback_target = "/parent/login?redirect-to=" + quote(redirect_to, safe="")
        # "google" here is the Social Login Key docname, not the display label.
        return get_oauth2_authorize_url("google", callback_target)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "parent/login: google oauth url failed")
        return None


def _load_settings(context):
    try:
        s = frappe.get_single("Parent Portal Settings")
        context.primary_color    = s.get("primary_color")   or "#2b2e4a"
        context.secondary_color  = s.get("secondary_color") or "#920c24"
        context.portal_title     = s.get("portal_title")    or "Parent Portal"
        context.portal_tagline   = s.get("portal_subtitle") or "Track your child's progress, attendance, and fees"
        context.portal_logo      = frappe.db.get_single_value("Institution Settings", "logo") or ""
    except Exception:
        frappe.log_error(frappe.get_traceback(), "parent/login: settings load failed")
        context.primary_color   = "#2b2e4a"
        context.secondary_color = "#920c24"
        context.portal_title    = "Parent Portal"
        context.portal_tagline  = "Track your child's progress, attendance, and fees"
        context.portal_logo     = ""
