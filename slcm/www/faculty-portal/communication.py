import frappe
from slcm.utils.faculty_portal import get_faculty_name, set_faculty_nav, set_nav_defaults

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "communication"

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

        # ── Portal Announcements ────────────────────────────────────
        announcements = frappe.get_all(
            "Portal Announcement",
            filters={"is_published": 1},
            fields=["name", "title", "content", "category", "priority",
                    "creation", "start_date", "end_date"],
            order_by="creation desc",
            limit=30,
            ignore_permissions=True,
        )
        for ann in announcements:
            ann["created_fmt"] = frappe.utils.formatdate(ann.creation, "dd MMM yyyy")
            priority = ann.priority or "Normal"
            ann["priority_class"] = {
                "Urgent":    "fp-badge-danger",
                "Important": "fp-badge-warning",
                "Normal":    "fp-badge-info",
            }.get(priority, "fp-badge-neutral")

        context.announcements = announcements

        # ── Category filter options ────────────────────────────────
        categories = sorted(set(
            ann.category for ann in announcements if ann.category
        ))
        context.categories = categories

    except Exception as e:
        frappe.log_error(f"Faculty Portal Communication error: {e}", "Faculty Portal")
        context.portal_error = str(e)
        set_nav_defaults(context)
        _set_defaults(context)

    return context


def _set_defaults(context):
    context.announcements = []
    context.categories = []
