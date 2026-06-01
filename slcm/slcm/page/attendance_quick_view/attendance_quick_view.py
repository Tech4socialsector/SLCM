import frappe
from slcm.permissions import (
    _get_faculty_name,
    _get_faculty_assigned_groups,
    _get_faculty_assigned_students,
    _FULL_ACCESS_ROLES,
)


def _is_unrestricted(roles):
    return bool(roles & _FULL_ACCESS_ROLES) or "slcm_Programme Chair" in roles


def _faculty_scope(user):
    """
    Return (groups, students, faculty_name) for the current faculty user,
    or (None, None, None) if the user has unrestricted access.
    Raises PermissionError if faculty has no linked Faculty record.
    """
    roles = set(frappe.get_roles(user))

    if _is_unrestricted(roles):
        return None, None, None

    if "slcm_Faculty" not in roles:
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    faculty_name = _get_faculty_name(user)
    if not faculty_name:
        frappe.throw(frappe._("No Faculty record linked to your account."), frappe.PermissionError)

    groups = _get_faculty_assigned_groups(faculty_name)
    students = _get_faculty_assigned_students(faculty_name)
    return groups, students, faculty_name


@frappe.whitelist()
def get_faculty_context():
    """
    Return the programmes, student groups, and sections visible to the
    current user so the JS can restrict filter dropdowns accordingly.
    Returns None for each when the user has unrestricted access.
    """
    user = frappe.session.user
    groups, students, faculty_name = _faculty_scope(user)

    if groups is None:
        # Unrestricted user — no restriction needed
        return {"restricted": False}

    if not groups:
        return {"restricted": True, "programmes": [], "groups": [], "sections": [], "course_offerings": []}

    # Derive visible programmes, sections, course offerings from assigned groups
    group_docs = frappe.get_all(
        "Student Group",
        filters={"name": ["in", groups]},
        fields=["name", "program", "section", "batch", "academic_year"],
    )

    programmes = list({g.program for g in group_docs if g.program})
    sections = list({g.section for g in group_docs if g.section})

    # Course offerings linked to these groups via Student Attendance
    course_offerings = frappe.get_all(
        "Student Attendance",
        filters={"student_group": ["in", groups]},
        fields=["course_offer"],
        distinct=True,
        pluck="course_offer",
    )
    course_offerings = [c for c in course_offerings if c]

    return {
        "restricted": True,
        "faculty_name": faculty_name,
        "groups": groups,
        "programmes": programmes,
        "sections": sections,
        "course_offerings": course_offerings,
    }


@frappe.whitelist()
def get_attendance_data(
    programme=None,
    course_offering=None,
    from_date=None,
    to_date=None,
    period=None,
    status=None,
    section=None,
):
    user = frappe.session.user
    groups, students, faculty_name = _faculty_scope(user)

    conditions = []
    values = {}

    # --- Faculty scoping: restrict to their student groups ---
    if groups is not None:
        if not groups:
            # Faculty exists but has no groups — return empty
            return {"data": [], "summary": {"total": 0, "present": 0, "absent": 0, "late": 0, "od": 0, "excused": 0}}

        placeholders = ", ".join(["%s"] * len(groups))
        conditions.append(f"sa.student_group IN ({placeholders})")
        values["_groups"] = groups  # handled separately below

    if from_date:
        conditions.append("sa.attendance_date >= %(from_date)s")
        values["from_date"] = from_date
    if to_date:
        conditions.append("sa.attendance_date <= %(to_date)s")
        values["to_date"] = to_date
    if programme:
        conditions.append("sa.program = %(programme)s")
        values["programme"] = programme
    if course_offering:
        conditions.append("sa.course_offer = %(course_offering)s")
        values["course_offering"] = course_offering
    if period:
        conditions.append("sa.period = %(period)s")
        values["period"] = period
    if status:
        conditions.append("sa.status = %(status)s")
        values["status"] = status
    if section:
        conditions.append("ss.section = %(section)s")
        values["section"] = section

    # Build the section join only when needed
    section_join = (
        "LEFT JOIN `tabStudent Group` ss ON sa.student_group = ss.name"
        if section else ""
    )

    # Rebuild conditions and values without the _groups sentinel,
    # because frappe.db.sql needs positional args for the IN clause
    if groups is not None and groups:
        group_placeholders = ", ".join(["%s"] * len(groups))
        group_condition = f"sa.student_group IN ({group_placeholders})"
        other_conditions = [c for c in conditions if "_groups" not in c and "student_group IN" not in c]
        all_conditions = [group_condition] + other_conditions
        where_clause = "WHERE " + " AND ".join(all_conditions)

        # Build positional args: groups first, then named values
        named_values = {k: v for k, v in values.items() if k != "_groups"}
        # frappe.db.sql supports %(name)s for named params — use that approach
        named_group_cond = "sa.student_group IN ({})".format(
            ", ".join(frappe.db.escape(g) for g in groups)
        )
        other_conds = [c for c in conditions if "student_group IN" not in c and "_groups" not in c]
        all_conds = [named_group_cond] + other_conds
        where_clause = "WHERE " + " AND ".join(all_conds)
        query_values = {k: v for k, v in values.items() if k != "_groups"}
    else:
        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query_values = {k: v for k, v in values.items() if k != "_groups"}

    data = frappe.db.sql(
        f"""
        SELECT
            sa.name,
            sa.student,
            sa.student_name,
            sa.attendance_date,
            sa.status,
            sa.course,
            sa.program,
            sa.course_offer,
            sa.period,
            sa.session_type,
            sa.in_time,
            sa.out_time,
            sa.student_group,
            sa.attendance_session
        FROM `tabStudent Attendance` sa
        {section_join}
        {where_clause}
        ORDER BY sa.attendance_date DESC, sa.student_name ASC
        LIMIT 500
        """,
        query_values,
        as_dict=True,
    )

    total = len(data)
    present = sum(1 for r in data if r.status == "Present")
    absent  = sum(1 for r in data if r.status == "Absent")
    late    = sum(1 for r in data if r.status == "Late")
    od      = sum(1 for r in data if r.status == "OD")
    excused = sum(1 for r in data if r.status == "Excused")

    return {
        "data": data,
        "summary": {
            "total": total,
            "present": present,
            "absent": absent,
            "late": late,
            "od": od,
            "excused": excused,
        },
    }


@frappe.whitelist()
def get_course_offerings(programme=None):
    user = frappe.session.user
    groups, students, faculty_name = _faculty_scope(user)

    filters = {}
    if programme:
        filters["program"] = programme

    if groups is not None:
        if not groups:
            return []
        # Only course offerings that appear in the faculty's student attendance records
        visible = frappe.get_all(
            "Student Attendance",
            filters={"student_group": ["in", groups]},
            fields=["course_offer"],
            distinct=True,
            pluck="course_offer",
        )
        visible = [c for c in visible if c]
        if not visible:
            return []
        filters["name"] = ["in", visible]

    return frappe.get_all(
        "Course Offering",
        filters=filters,
        fields=["name", "course_title"],
        order_by="course_title asc",
        limit=200,
    )


@frappe.whitelist()
def get_sections(programme=None, course_offering=None):
    user = frappe.session.user
    groups, students, faculty_name = _faculty_scope(user)

    filters = {}
    if programme:
        filters["program"] = programme

    if groups is not None:
        if not groups:
            return []
        group_docs = frappe.get_all(
            "Student Group",
            filters={"name": ["in", groups]},
            pluck="section",
        )
        visible_sections = [s for s in group_docs if s]
        if not visible_sections:
            return []
        filters["name"] = ["in", visible_sections]

    return frappe.get_all(
        "Program Batch Section",
        filters=filters,
        fields=["name", "section_name"],
        order_by="section_name asc",
        limit=200,
    )
