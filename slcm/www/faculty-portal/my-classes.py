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
    context.active_page = "my_classes"

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

        # ── Fetch all course offerings for this faculty ────────────
        course_offerings = frappe.get_all(
            "Course Offering",
            filters={"faculty": faculty_name},
            fields=["name", "course_name", "course_title", "term_name",
                    "academic_year", "credit_value", "maximum_students", "status"],
            order_by="academic_year desc, term_name desc, course_name asc",
            ignore_permissions=True,
        )

        # ── Enrich each offering ───────────────────────────────────
        enriched = []
        for co in course_offerings:
            # Student count via enrollment (Student Group has no course_offering field)
            try:
                res = frappe.db.sql(
                    """SELECT COUNT(DISTINCT se.student) AS cnt
                       FROM `tabStudent Enrollment Course` sec
                       JOIN `tabStudent Enrollment` se ON se.name = sec.parent
                       WHERE sec.course_offering = %s AND sec.status = 'Enrolled'""",
                    co.name, as_dict=True,
                )
                student_count = (res[0].cnt or 0) if res else 0
            except Exception:
                student_count = 0

            # Average attendance from Attendance Sessions (direct, not Attendance Summary)
            try:
                att_data = frappe.db.sql(
                    """SELECT AVG(attendance_percentage) AS avg_pct
                       FROM `tabAttendance Session`
                       WHERE course_offering = %s AND attendance_marked = 1""",
                    co.name, as_dict=True,
                )
                avg_att = round(float((att_data[0].avg_pct or 0) if att_data else 0), 1)
            except Exception:
                avg_att = 0.0

            # Total sessions conducted
            total_sessions = frappe.db.count(
                "Attendance Session",
                filters={"course_offering": co.name, "attendance_marked": 1},
            )

            enriched.append({
                "name": co.name,
                "course_name": co.course_name or co.name,
                "term_name": co.term_name or "—",
                "academic_year": co.academic_year or "—",
                "credits": co.credit_value or 0,
                "student_count": student_count,
                "avg_attendance": avg_att,
                "total_sessions": total_sessions,
                "status": co.status or "Active",
                "group_count": 0,
            })

        context.course_offerings = enriched

        # ── Filter options ─────────────────────────────────────────
        terms = sorted(set(c["term_name"] for c in enriched if c["term_name"] != "—"))
        years = sorted(set(c["academic_year"] for c in enriched if c["academic_year"] != "—"), reverse=True)
        context.filter_terms = terms
        context.filter_years = years

    except Exception as e:
        frappe.log_error(f"Faculty Portal My Classes error: {e}", "Faculty Portal")
        context.portal_error = str(e)
        set_nav_defaults(context)
        _set_defaults(context)

    return context


def _set_defaults(context):
    context.course_offerings = []
    context.filter_terms = []
    context.filter_years = []
