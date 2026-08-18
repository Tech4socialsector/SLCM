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
    context.active_page = "support"

    faculty_name = get_faculty_name()
    if not faculty_name:
        context.not_a_faculty = True
        set_nav_defaults(context)
        return context

    context.not_a_faculty = False

    # Detect if the user has an Agent role — agents use the full helpdesk interface
    try:
        from helpdesk.utils import is_agent
        context.is_hd_agent = is_agent(frappe.session.user)
    except Exception:
        user_roles = frappe.get_roles(frappe.session.user)
        agent_roles = {
            "Agent",
            "Agent Manager",
            "HD Agent",
            "HD Manager",
            "System Manager",
            "Administrator",
        }
        context.is_hd_agent = bool(set(user_roles).intersection(agent_roles)) or bool(
            frappe.db.exists("HD Agent", {"user": frappe.session.user})
            or frappe.db.exists("HD Agent", frappe.session.user)
        )


    try:
        faculty = frappe.get_doc("Faculty", faculty_name)
        set_faculty_nav(context, faculty)
    except Exception as e:
        frappe.log_error(f"Faculty Portal Helpdesk error: {e}", "Faculty Portal")
        context.portal_error = str(e)
        set_nav_defaults(context)

    return context
