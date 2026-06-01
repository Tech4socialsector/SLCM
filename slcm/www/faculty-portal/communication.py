import frappe
from frappe.utils import nowdate, getdate
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

        faculty_department = getattr(faculty, "department", None) or ""
        today_str = nowdate()
        today_date = getdate(today_str)

        # ── Fetch all active, published Faculty Announcements ──────
        records = frappe.get_all(
            "Faculty Announcement",
            filters=[["is_active", "=", 1], ["publish_date", "<=", today_str]],
            fields=[
                "name", "title", "content", "announcement_type", "priority",
                "publish_date", "expiry_date", "target_audience",
            ],
            order_by="priority desc, publish_date desc",
            limit=50,
            ignore_permissions=True,
        )

        announcements = []
        for r in records:
            # skip expired
            if r.expiry_date and getdate(r.expiry_date) < today_date:
                continue

            # targeting filter
            if r.target_audience == "All Faculty":
                pass  # visible to everyone
            elif r.target_audience == "Specific Department(s)":
                target_depts = frappe.get_all(
                    "Announcement Department Target",
                    filters={"parent": r.name},
                    fields=["department"],
                    ignore_permissions=True,
                )
                if not any(t.department == faculty_department for t in target_depts):
                    continue
            elif r.target_audience == "Specific Faculty":
                target_faculties = frappe.get_all(
                    "Announcement Faculty Target",
                    filters={"parent": r.name},
                    fields=["faculty"],
                    ignore_permissions=True,
                )
                if not any(t.faculty == faculty_name for t in target_faculties):
                    continue

            priority = r.priority or "Normal"
            announcements.append({
                "name": r.name,
                "title": r.title,
                "content": r.content or "",
                "announcement_type": r.announcement_type or "General",
                "priority": priority,
                "publish_date": r.publish_date,
                "expiry_date": r.expiry_date,
                "target_audience": r.target_audience or "All Faculty",
                "publish_fmt": frappe.utils.formatdate(r.publish_date, "dd MMM yyyy"),
                "priority_class": {
                    "Urgent":    "fp-badge-danger",
                    "Important": "fp-badge-warning",
                    "Normal":    "fp-badge-info",
                }.get(priority, "fp-badge-neutral"),
                "type_icon": {
                    "Academic":       "school",
                    "Administrative": "admin_panel_settings",
                    "Examination":    "assignment",
                    "Research":       "science",
                    "General":        "campaign",
                }.get(r.announcement_type or "General", "campaign"),
            })

        context.announcements = announcements
        context.total_count     = len(announcements)
        context.urgent_count    = sum(1 for a in announcements if a["priority"] == "Urgent")
        context.important_count = sum(1 for a in announcements if a["priority"] == "Important")

        context.announcement_types = sorted(set(a["announcement_type"] for a in announcements))
        context.categories = context.announcement_types  # alias kept for template compatibility

    except Exception as e:
        frappe.log_error(f"Faculty Portal Communication error: {e}", "Faculty Portal")
        context.portal_error = str(e)
        set_nav_defaults(context)
        _set_defaults(context)

    return context


def _set_defaults(context):
    context.announcements = []
    context.categories = []
    context.announcement_types = []
    context.total_count = 0
    context.urgent_count = 0
    context.important_count = 0
