import frappe
from slcm.utils.faculty_portal import get_faculty_name, set_faculty_nav, set_nav_defaults, set_portal_settings

no_cache = 1


def get_context(context):
    context.no_cache = 1
    set_portal_settings(context)

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "settings"

    faculty_name = get_faculty_name()
    if not faculty_name:
        context.not_a_faculty = True
        set_nav_defaults(context)
        _set_defaults(context)
        return context

    context.not_a_faculty = False

    try:
        faculty = frappe.get_doc("Faculty", faculty_name, ignore_permissions=True)
        set_faculty_nav(context, faculty)

        # Load user preferences
        try:
            prefs = frappe.get_doc("Faculty Portal User Preferences", frappe.session.user)
            context.prefs = prefs.as_dict()
        except frappe.DoesNotExistError:
            context.prefs = {}

        # Load permission gates from Faculty Portal Settings
        try:
            settings = frappe.db.get_singles_dict("Faculty Portal Settings")
        except Exception:
            settings = {}

        context.gates = {
            "allow_theme_override":         bool(int(settings.get("allow_theme_override", 1))),
            "allow_font_size_override":      bool(int(settings.get("allow_font_size_override", 1))),
            "allow_density_override":        bool(int(settings.get("allow_density_override", 1))),
            "allow_dashboard_customization": bool(int(settings.get("allow_dashboard_customization", 1))),
            "allow_notification_settings":   bool(int(settings.get("allow_notification_settings", 1))),
        }

        context.faculty_email = frappe.session.user

    except Exception as e:
        frappe.log_error(f"Faculty Portal Settings page error: {e}", "Faculty Portal")
        context.portal_error = str(e)
        set_nav_defaults(context)
        _set_defaults(context)

    return context


def _set_defaults(context):
    context.prefs = {}
    context.gates = {}
    context.faculty_email = ""
