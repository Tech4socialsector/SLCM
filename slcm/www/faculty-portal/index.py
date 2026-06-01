import frappe
from slcm.utils.faculty_portal import get_faculty_name, set_faculty_nav, set_nav_defaults, fmt_time

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "dashboard"

    faculty_name = get_faculty_name()
    if not faculty_name:
        context.not_a_faculty = True
        set_nav_defaults(context)
        return context

    context.not_a_faculty = False

    try:
        faculty = frappe.get_doc("Faculty", faculty_name, ignore_permissions=True)
        set_faculty_nav(context, faculty)

        today = frappe.utils.today()

        # ── Course Offerings assigned to this faculty ──────────────
        course_offerings = frappe.get_all(
            "Course Offering",
            filters={"faculty": faculty_name, "status": "Active"},
            fields=["name", "course_name", "course_title", "term_name",
                    "academic_year", "credit_value", "maximum_students"],
            ignore_permissions=True,
        )
        context.total_subjects = len(course_offerings)
        co_names = [c.name for c in course_offerings]

        # ── Total unique students across all course offerings ──────
        total_students = 0
        if co_names:
            try:
                groups = frappe.get_all(
                    "Student Group",
                    filters={"course_offering": ["in", co_names]},
                    fields=["name", "course_offering"],
                    ignore_permissions=True,
                )
                group_names = [g.name for g in groups]
                if group_names:
                    student_count = frappe.db.sql(
                        """SELECT COUNT(DISTINCT student) AS cnt
                           FROM `tabStudent Group Student`
                           WHERE parent IN %s AND active = 1""",
                        (tuple(group_names),),
                        as_dict=True,
                    )
                    total_students = (student_count[0].cnt or 0) if student_count else 0
            except Exception:
                total_students = 0
        context.total_students = total_students

        # ── Today's sessions ────────────────────────────────────────
        todays_sessions = []
        if co_names:
            try:
                raw = frappe.get_all(
                    "Attendance Session",
                    filters=[
                        ["course_offering", "in", co_names],
                        ["session_date", "=", today],
                    ],
                    fields=["name", "course_offering", "session_date",
                            "session_start_time", "session_end_time",
                            "room", "session_status", "total_students",
                            "present_count", "attendance_percentage"],
                    order_by="session_start_time asc",
                    ignore_permissions=True,
                )
                co_map = {c.name: c for c in course_offerings}
                for s in raw:
                    co = co_map.get(s.course_offering, frappe._dict())
                    todays_sessions.append({
                        "name": s.name,
                        "course_name": co.get("course_name") or s.course_offering,
                        "from_time": fmt_time(s.session_start_time),
                        "to_time": fmt_time(s.session_end_time),
                        "venue": s.room or "—",
                        "status": s.session_status or "Active",
                        "total_students": s.total_students or 0,
                        "present_count": s.present_count or 0,
                        "attendance_pct": round(float(s.attendance_percentage or 0), 1),
                        "attendance_marked": bool(s.present_count),
                    })
            except Exception:
                todays_sessions = []
        context.todays_sessions = todays_sessions
        context.todays_class_count = len(todays_sessions)

        # ── Attendance pending (sessions not yet marked today/recent) ─
        try:
            pending_att = frappe.db.count(
                "Attendance Session",
                filters={
                    "course_offering": ["in", co_names] if co_names else ["in", ["__none__"]],
                    "attendance_marked": 0,
                    "session_date": ["<=", today],
                    "session_status": "Active",
                },
            ) if co_names else 0
        except Exception:
            pending_att = 0
        context.attendance_pending = pending_att

        # ── Upcoming class schedule (next 7 days) ──────────────────
        next_week = frappe.utils.add_days(today, 7)
        upcoming_classes = []
        if co_names:
            try:
                upcoming_raw = frappe.get_all(
                    "Attendance Session",
                    filters=[
                        ["course_offering", "in", co_names],
                        ["session_date", ">", today],
                        ["session_date", "<=", next_week],
                    ],
                    fields=["name", "course_offering", "session_date",
                            "session_start_time", "session_end_time", "room"],
                    order_by="session_date asc, session_start_time asc",
                    limit=8,
                    ignore_permissions=True,
                )
                co_map = {c.name: c for c in course_offerings}
                for s in upcoming_raw:
                    co = co_map.get(s.course_offering, frappe._dict())
                    upcoming_classes.append({
                        "course_name": co.get("course_name") or s.course_offering,
                        "session_date": frappe.utils.formatdate(s.session_date, "dd MMM"),
                        "from_time": fmt_time(s.session_start_time),
                        "to_time": fmt_time(s.session_end_time),
                        "venue": s.room or "—",
                    })
            except Exception:
                upcoming_classes = []
        context.upcoming_classes = upcoming_classes

        # ── Pending venue bookings ──────────────────────────────────
        try:
            pending_venues = frappe.db.count(
                "Venue Booking",
                filters={"requester_name": faculty_name, "status": "Pending"},
            )
        except Exception:
            pending_venues = 0
        context.pending_venues = pending_venues

        # ── Condonation requests pending faculty recommendation ────
        try:
            pending_condonation = frappe.db.count(
                "Student Attendance Condonation",
                filters={
                    "course_offering": ["in", co_names] if co_names else ["in", ["__none__"]],
                    "faculty_recommendation": ["in", ["", None]],
                    "final_status": "Pending",
                },
            ) if co_names else 0
        except Exception:
            pending_condonation = 0
        context.pending_condonation = pending_condonation

        # ── Recent attendance sessions (last 5) ─────────────────────
        recent_sessions = []
        if co_names:
            try:
                recent_raw = frappe.get_all(
                    "Attendance Session",
                    filters=[
                        ["course_offering", "in", co_names],
                        ["session_date", "<", today],
                    ],
                    fields=["name", "course_offering", "session_date",
                            "total_students", "present_count", "absent_count",
                            "attendance_percentage", "attendance_marked"],
                    order_by="session_date desc",
                    limit=5,
                    ignore_permissions=True,
                )
                co_map = {c.name: c for c in course_offerings}
                for s in recent_raw:
                    co = co_map.get(s.course_offering, frappe._dict())
                    recent_sessions.append({
                        "course_name": co.get("course_name") or s.course_offering,
                        "session_date": frappe.utils.formatdate(s.session_date, "dd MMM yyyy"),
                        "total": s.total_students or 0,
                        "present": s.present_count or 0,
                        "absent": s.absent_count or 0,
                        "pct": round(float(s.attendance_percentage or 0), 1),
                        "marked": bool(s.attendance_marked),
                    })
            except Exception:
                recent_sessions = []
        context.recent_sessions = recent_sessions

        # ── Academic Year ───────────────────────────────────────────
        context.current_academic_year = ""
        if course_offerings:
            context.current_academic_year = course_offerings[0].academic_year or ""

        context.faculty_status = faculty.status or "Active"

    except Exception as e:
        frappe.log_error(f"Faculty Portal Dashboard error: {e}", "Faculty Portal")
        context.portal_error = str(e)
        set_nav_defaults(context)
        _set_defaults(context)

    return context


def _set_defaults(context):
    context.total_subjects = 0
    context.total_students = 0
    context.todays_class_count = 0
    context.todays_sessions = []
    context.attendance_pending = 0
    context.upcoming_classes = []
    context.pending_venues = 0
    context.pending_condonation = 0
    context.recent_sessions = []
    context.current_academic_year = ""
    context.faculty_status = "Active"
