import frappe
from slcm.slcm.doctype.parent_portal_settings.parent_portal_settings import get_parent_portal_settings


def get_parent_context(context):
    """
    Shared setup for all parent portal pages.
    Resolves which student(s) the logged-in user is a parent of,
    sets nav variables, and returns the active Student Master doc.

    Returns the active Student Master doc, or None if not a parent.
    """
    context.no_cache = 1

    user = frappe.session.user
    if user == "Guest":
        context.is_guest = True
        context.not_a_parent = False
        try:
            context.pp_settings = get_parent_portal_settings()
        except Exception:
            context.pp_settings = {}
        return None

    context.is_guest = False

    # Find all students where this user's email is in the parents child table
    rows = frappe.db.sql(
        """
        SELECT sm.name, sm.first_name, sm.last_name, sm.programme,
               sm.batch_year, sm.student_status, sm.passport_size_photo
        FROM   `tabStudent Master` sm
        INNER JOIN `tabStudent Parent` sp
               ON sp.parent = sm.name AND sp.parenttype = 'Student Master'
        WHERE  sp.email = %s
        ORDER  BY sm.first_name
        """,
        user,
        as_dict=True,
    )

    if not rows:
        context.not_a_parent = True
        context.is_guest = False
        context.parent_display_name = ""
        context.parent_initial = "?"
        try:
            context.pp_settings = get_parent_portal_settings()
        except Exception:
            context.pp_settings = {}
        return None

    context.not_a_parent = False

    # Parent display name from Frappe User
    user_doc = frappe.db.get_value("User", user, ["first_name", "last_name", "full_name"], as_dict=True)
    if user_doc:
        context.parent_display_name = (
            user_doc.full_name
            or f"{user_doc.first_name or ''} {user_doc.last_name or ''}".strip()
            or user
        )
    else:
        context.parent_display_name = user
    context.parent_initial = (context.parent_display_name or "P")[0].upper()

    context.wards = rows

    # Active ward: from ?ward= query param, default to first
    active_ward = frappe.request.args.get("ward") if frappe.request else None
    ward_names = [r.name for r in rows]
    if active_ward not in ward_names:
        active_ward = ward_names[0]

    context.active_ward = active_ward

    student = next((r for r in rows if r.name == active_ward), rows[0])
    context.ward_name = f"{student.first_name} {student.last_name or ''}".strip()
    context.ward_initial = (student.first_name or "S")[0].upper()
    context.ward_photo = student.passport_size_photo or ""
    context.ward_status = student.student_status or ""

    # Programme display name
    context.ward_programme = ""
    if student.programme:
        prog_name = frappe.db.get_value("Batch", student.programme, "cohort_name")
        context.ward_programme = prog_name or student.programme

    context.ward_batch = student.batch_year or ""

    # Inject portal settings so all pages can access pp_settings in templates
    try:
        context.pp_settings = get_parent_portal_settings()
    except Exception:
        context.pp_settings = {}

    return frappe.get_doc("Student Master", active_ward, ignore_permissions=True)
