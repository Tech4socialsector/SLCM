import frappe
from slcm.utils.faculty_portal import get_faculty_name, set_faculty_nav, set_nav_defaults, set_portal_settings

no_cache = 1


def get_context(context):
    context.no_cache = 1
    set_portal_settings(context)
    _set_defaults(context)

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "course_offerings"
    context.not_a_faculty = False

    faculty_name = get_faculty_name()
    if not faculty_name:
        context.not_a_faculty = True
        set_nav_defaults(context)
        return context

    try:
        faculty = frappe.get_doc("Faculty", faculty_name, ignore_permissions=True)
        set_faculty_nav(context, faculty)
    except Exception as e:
        frappe.log_error(f"Faculty Portal Course Offerings - faculty load error: {e}", "Faculty Portal")
        context.not_a_faculty = True
        set_nav_defaults(context)
        return context

    try:
        raw_offerings = frappe.get_all(
            "Course Offering",
            filters={"faculty": faculty_name},
            fields=["name", "course_name", "term_name", "academic_year",
                    "credit_value", "maximum_students", "status"],
            order_by="academic_year desc, term_name asc, course_name asc",
            ignore_permissions=True,
        )

        enriched = []
        for co in raw_offerings:
            student_count = _get_student_count(co.name)
            avg_att, sessions_done = _get_attendance(co.name)
            enriched.append({
                "name": co.name,
                "course_name": co.course_name or co.name,
                "term_name": co.term_name or "—",
                "academic_year": co.academic_year or "—",
                "credits": co.credit_value or 0,
                "student_count": student_count,
                "avg_attendance": avg_att,
                "sessions_done": sessions_done,
                "status": co.status or "Open",
            })

        context.course_offerings = enriched
        context.filter_terms = sorted(
            set(c["term_name"] for c in enriched if c["term_name"] != "—")
        )
        context.filter_years = sorted(
            set(c["academic_year"] for c in enriched if c["academic_year"] != "—"),
            reverse=True,
        )

        # Summary stats
        context.total_courses = len(enriched)
        context.total_students = sum(c["student_count"] for c in enriched)
        context.total_sessions = sum(c["sessions_done"] for c in enriched)
        context.active_courses = sum(
            1 for c in enriched if c["status"] in ("Open", "Active")
        )
        att_values = [c["avg_attendance"] for c in enriched if c["avg_attendance"] > 0]
        context.overall_avg_att = (
            round(sum(att_values) / len(att_values), 1) if att_values else 0.0
        )

    except Exception as e:
        frappe.log_error(
            f"Faculty Portal Course Offerings error for faculty {faculty_name}: {e}",
            "Faculty Portal",
        )
        context.portal_error = str(e)

    return context


def _get_student_count(co_name):
    try:
        res = frappe.db.sql(
            """SELECT COUNT(DISTINCT se.student) AS cnt
               FROM `tabStudent Enrollment Course` sec
               JOIN `tabStudent Enrollment` se ON se.name = sec.parent
               WHERE sec.course_offering = %s AND sec.status = 'Enrolled'""",
            co_name,
            as_dict=True,
        )
        return (res[0].cnt or 0) if res else 0
    except Exception:
        return 0


def _get_attendance(co_name):
    try:
        rows = frappe.db.sql(
            """SELECT AVG(attendance_percentage) AS avg_pct, COUNT(*) AS sess
               FROM `tabAttendance Session`
               WHERE course_offering = %s AND attendance_marked = 1""",
            co_name,
            as_dict=True,
        )
        avg_pct = round(float((rows[0].avg_pct or 0) if rows else 0), 1)
        sessions = int((rows[0].sess or 0) if rows else 0)
        return avg_pct, sessions
    except Exception:
        return 0.0, 0


def _set_defaults(context):
    context.is_guest = False
    context.not_a_faculty = False
    context.course_offerings = []
    context.filter_terms = []
    context.filter_years = []
    context.total_courses = 0
    context.total_students = 0
    context.total_sessions = 0
    context.active_courses = 0
    context.overall_avg_att = 0.0
    context.portal_error = None
