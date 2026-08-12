from urllib.parse import quote

import frappe
from frappe.utils.oauth import get_oauth2_authorize_url

from slcm.slcm.utils.parent_portal import get_parent_wards
from slcm.utils.faculty_portal import get_faculty_name


no_cache = 1

TAB_FACULTY_STUDENT = "faculty-student"
TAB_PARENT = "parent"


def get_context(context):
    redirect_to = (
        frappe.local.request.args.get("redirect-to", "") or
        frappe.local.request.args.get("redirect_to", "") or
        frappe.local.request.args.get("redirect", "") or
        frappe.local.request.args.get("next", "")
    )

    requested_tab = frappe.local.request.args.get("tab", "")
    default_tab = getattr(frappe.local.flags, "default_login_tab", None)
    tab = requested_tab or default_tab or TAB_FACULTY_STUDENT
    if tab not in (TAB_FACULTY_STUDENT, TAB_PARENT):
        tab = TAB_FACULTY_STUDENT

    if frappe.session.user != "Guest":
        user = frappe.session.user
        user_type = frappe.db.get_value("User", user, "user_type") or "Website User"

        if get_faculty_name():
            frappe.local.flags.redirect_location = redirect_to or "/faculty-portal"
            raise frappe.Redirect

        if frappe.db.exists("Student Master", {"official_email_id": user}) or \
           frappe.db.exists("Student Master", {"user": user}):
            frappe.local.flags.redirect_location = redirect_to or "/student-portal"
            raise frappe.Redirect

        if get_parent_wards(user):
            frappe.local.flags.redirect_location = redirect_to or "/parent-portal"
            raise frappe.Redirect

        if user_type == "System User":
            frappe.local.flags.redirect_location = "/desk"
            raise frappe.Redirect

        # Logged-in Google account has no linked Student/Faculty/Parent record —
        # sign them back out and show the error inline instead of forwarding
        # them to a bare, disconnected portal page.
        frappe.local.login_manager.logout()
        frappe.db.commit()
        context.no_role_found = True

    context.tab = tab
    context.redirect_to = redirect_to

    _load_settings(context)

    context.no_cache = 1
    context.csrf_token = frappe.local.session.data.csrf_token or ""
    context.title = context.portal_title + " — Login"
    context.google_login_url_faculty_student = _get_google_login_url(TAB_FACULTY_STUDENT, redirect_to)
    context.google_login_url_parent = _get_google_login_url(TAB_PARENT, redirect_to)
    context.google_login_error = frappe.local.request.args.get("error", "")


def _get_google_login_url(tab, redirect_to):
    # Returns the URL that starts the Google OAuth flow (redirects to Google's
    # consent screen), or None if Google login isn't configured/enabled for
    # this tab — in which case the "Continue with Google" button is hidden.
    settings_doctype = "Parent Portal Settings" if tab == TAB_PARENT else "Student Portal Settings"
    if not frappe.db.get_single_value(settings_doctype, "enable_google_login"):
        return None
    if not frappe.db.exists(
        "Social Login Key",
        {"social_login_provider": "Google", "enable_social_login": 1}
    ):
        return None
    try:
        # Send the OAuth callback back to this login page (not straight to a
        # portal) so the already-logged-in role-detection above always runs
        # first, and the browser lands back on the tab it started from if
        # the login is rejected. The real destination is carried through as
        # a query param and honored once the role check passes.
        callback_target = f"/login?tab={tab}&redirect-to=" + quote(redirect_to, safe="")
        # "google" here is the Social Login Key docname, not the display label.
        return get_oauth2_authorize_url("google", callback_target)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "portal-login/login: google oauth url failed")
        return None


def _load_settings(context):
    try:
        context.primary_color = "#2b2e4a"
        context.secondary_color = "#920c24"
        context.portal_title = "Institution Portal"
        context.portal_tagline = "Access your courses, classes, or your child's progress — all in one place"
        context.portal_logo = frappe.db.get_single_value("Institution Settings", "logo") or ""
    except Exception:
        frappe.log_error(frappe.get_traceback(), "portal-login/login: settings load failed")
        context.primary_color = "#2b2e4a"
        context.secondary_color = "#920c24"
        context.portal_title = "Institution Portal"
        context.portal_tagline = "Access your courses, classes, or your child's progress — all in one place"
        context.portal_logo = ""
