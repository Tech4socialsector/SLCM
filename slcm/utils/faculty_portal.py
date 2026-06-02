import frappe
from slcm.slcm.doctype.faculty_portal_settings.faculty_portal_settings import (
    get_faculty_portal_settings,
)


def get_faculty_name():
    user = frappe.session.user
    name = frappe.db.get_value("Faculty", {"user_id": user}, "name")
    if not name:
        name = frappe.db.get_value("Faculty", {"email": user}, "name")
    if name:
        try:
            if not frappe.db.get_value("Faculty", name, "user_id"):
                frappe.db.set_value("Faculty", name, "user_id", user, update_modified=False)
        except Exception:
            pass
    return name


def set_faculty_nav(context, faculty):
    full_name = " ".join(filter(None, [faculty.first_name, faculty.last_name]))
    context.faculty_name = full_name or faculty.name
    context.faculty_id = faculty.faculty_id or faculty.name
    context.faculty_photo = faculty.photo or ""
    context.faculty_initial = (context.faculty_name[0]).upper() if context.faculty_name else "F"
    context.faculty_email = faculty.email or frappe.session.user
    context.faculty_designation = faculty.designation or ""
    context.faculty_department = (
        frappe.db.get_value("Department", faculty.department, "department_name")
        if faculty.department
        else faculty.department or ""
    )


def set_portal_settings(context):
    """Load Faculty Portal Settings into context.fp_settings for template use."""
    try:
        context.fp_settings = get_faculty_portal_settings()
    except Exception:
        context.fp_settings = {}


def set_nav_defaults(context):
    user = frappe.session.user
    user_doc = frappe.db.get_value("User", user, ["full_name", "user_image"], as_dict=True)
    context.faculty_name = (user_doc.full_name if user_doc else "") or user.split("@")[0]
    context.faculty_id = ""
    context.faculty_photo = (user_doc.user_image if user_doc else "") or ""
    context.faculty_initial = (context.faculty_name[0]).upper() if context.faculty_name else "F"
    context.faculty_email = user
    context.faculty_designation = ""
    context.faculty_department = ""


def fmt_time(t):
    if not t:
        return ""
    try:
        if hasattr(t, "seconds"):
            total = int(t.seconds)
            h, rem = divmod(total, 3600)
            m = rem // 60
        else:
            parts = str(t).split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
        suffix = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {suffix}"
    except Exception:
        return str(t)
