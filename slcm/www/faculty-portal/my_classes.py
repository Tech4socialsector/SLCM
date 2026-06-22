import frappe
from slcm.utils.faculty_portal import get_faculty_name, set_faculty_nav, set_nav_defaults, set_portal_settings, fmt_time

no_cache = 1


def get_context(context):
    context.no_cache = 1
    set_portal_settings(context)
    _set_defaults(context)

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "my_classes"

    faculty_name = get_faculty_name()
    if not faculty_name:
        context.not_a_faculty = True
        set_nav_defaults(context)
        return context

    context.not_a_faculty = False

    try:
        faculty = frappe.get_doc("Faculty", faculty_name)
        set_faculty_nav(context, faculty)

        today = frappe.utils.today()

        # ── Fetch all course offerings for this faculty ────────────
        raw_offerings = frappe.get_all(
            "Course Offering",
            filters={"faculty": faculty_name},
            fields=["name", "course_name", "course_title", "term_name",
                    "academic_year", "credit_value", "maximum_students", "status"],
            order_by="academic_year desc, term_name asc, course_name asc",
            ignore_permissions=True,
        )

        # ── Enrich each offering ───────────────────────────────────
        enriched = []
        for co in raw_offerings:
            student_count = _get_student_count(co.name)
            avg_att, total_sessions = _get_attendance(co.name)
            pending = _get_pending_sessions(co.name, today)
            next_session = _get_next_session(co.name, today)
            students = _get_students(co.name)
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
                "pending_sessions": pending,
                "next_session": next_session,
                "students": students,
                "group_count": 0,
            })

        context.course_offerings = enriched

        # ── Filter options ─────────────────────────────────────────
        context.filter_terms = sorted(set(c["term_name"] for c in enriched if c["term_name"] != "—"))
        context.filter_years = sorted(set(c["academic_year"] for c in enriched if c["academic_year"] != "—"), reverse=True)

        # ── Summary stats ──────────────────────────────────────────
        context.total_courses = len(enriched)
        context.total_students = sum(c["student_count"] for c in enriched)
        context.total_sessions = sum(c["total_sessions"] for c in enriched)
        context.active_courses = sum(1 for c in enriched if c["status"] in ("Open", "Active"))

    except Exception as e:
        frappe.log_error(str(e)[:130], "Faculty Portal My Classes")
        context.portal_error = str(e)
        set_nav_defaults(context)
        _set_defaults(context)

    return context


def _get_student_count(co_name):
    try:
        res = frappe.db.sql(
            """SELECT COUNT(DISTINCT se.student) AS cnt
               FROM `tabStudent Enrollment Course` sec
               JOIN `tabStudent Enrollment` se ON se.name = sec.parent
               WHERE sec.course_offering = %s AND sec.status = 'Enrolled'""",
            co_name, as_dict=True,
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
            co_name, as_dict=True,
        )
        avg_pct = round(float((rows[0].avg_pct or 0) if rows else 0), 1)
        sessions = int((rows[0].sess or 0) if rows else 0)
        return avg_pct, sessions
    except Exception:
        return 0.0, 0


def _get_pending_sessions(co_name, today):
    """Count sessions that are past/today and have not been marked."""
    try:
        res = frappe.db.sql(
            """SELECT COUNT(*) AS cnt FROM `tabAttendance Session`
               WHERE course_offering = %s AND attendance_marked = 0
               AND session_date <= %s""",
            (co_name, today), as_dict=True,
        )
        return int((res[0].cnt or 0) if res else 0)
    except Exception:
        return 0


def _get_next_session(co_name, today):
    """Return the next upcoming session date/time/room."""
    try:
        rows = frappe.db.sql(
            """SELECT session_date, session_start_time, session_end_time, room
               FROM `tabAttendance Session`
               WHERE course_offering = %s AND session_date >= %s
               ORDER BY session_date ASC, session_start_time ASC LIMIT 1""",
            (co_name, today), as_dict=True,
        )
        if rows:
            s = rows[0]
            return {
                "date": frappe.utils.formatdate(s.session_date, "dd MMM"),
                "from_time": fmt_time(s.session_start_time),
                "to_time": fmt_time(s.session_end_time),
                "room": s.room or "—",
            }
        return None
    except Exception:
        return None


def _get_students(co_name):
    """Return list of enrolled students for a course offering."""
    try:
        rows = frappe.db.sql(
            """SELECT se.student AS student_id, se.student_name
               FROM `tabStudent Enrollment Course` sec
               JOIN `tabStudent Enrollment` se ON se.name = sec.parent
               WHERE sec.course_offering = %s AND sec.status = 'Enrolled'
               ORDER BY se.student_name""",
            co_name, as_dict=True,
        )
        return [{"id": r.student_id, "name": (r.student_name or r.student_id or "—")} for r in rows]
    except Exception:
        return []


def _set_defaults(context):
    context.course_offerings = []
    context.filter_terms = []
    context.filter_years = []
    context.total_courses = 0
    context.total_students = 0
    context.total_sessions = 0
    context.active_courses = 0
    context.portal_error = None
