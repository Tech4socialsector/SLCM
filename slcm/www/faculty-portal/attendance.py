import frappe
from slcm.utils.faculty_portal import get_faculty_name, set_faculty_nav, set_nav_defaults, fmt_time

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "attendance"

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

        today = frappe.utils.today()

        # ── Course offerings ────────────────────────────────────────
        course_offerings = frappe.get_all(
            "Course Offering",
            filters={"faculty": faculty_name, "status": "Active"},
            fields=["name", "course_name", "term_name", "academic_year"],
            order_by="course_name asc",
            ignore_permissions=True,
        )
        context.course_offerings = course_offerings
        co_names = [c.name for c in course_offerings]
        co_map = {c.name: c for c in course_offerings}

        # ── Filter from URL params ──────────────────────────────────
        selected_co = frappe.request.args.get("course_offering", "") if frappe.request else ""
        context.selected_co = selected_co

        # ── Attendance Sessions ─────────────────────────────────────
        session_filters = [["course_offering", "in", co_names]] if co_names else [["name", "=", "__none__"]]
        if selected_co and selected_co in co_names:
            session_filters = [["course_offering", "=", selected_co]]

        sessions = []
        if co_names:
            raw_sessions = frappe.get_all(
                "Attendance Session",
                filters=session_filters,
                fields=["name", "course_offering", "session_date", "session_type",
                        "session_start_time", "session_end_time", "room",
                        "session_status", "total_students", "present_count",
                        "absent_count", "attendance_percentage", "attendance_marked"],
                order_by="session_date desc",
                limit=50,
                ignore_permissions=True,
            )
            for s in raw_sessions:
                co = co_map.get(s.course_offering, frappe._dict())
                pct = round(float(s.attendance_percentage or 0), 1)
                sessions.append({
                    "name": s.name,
                    "course_name": co.get("course_name") or s.course_offering,
                    "course_offering": s.course_offering,
                    "session_date": s.session_date,
                    "session_date_fmt": frappe.utils.formatdate(s.session_date, "dd MMM yyyy"),
                    "session_type": s.session_type or "Lecture",
                    "from_time": fmt_time(s.session_start_time),
                    "to_time": fmt_time(s.session_end_time),
                    "venue": s.room or "—",
                    "status": s.session_status or "Active",
                    "total": s.total_students or 0,
                    "present": s.present_count or 0,
                    "absent": s.absent_count or 0,
                    "pct": pct,
                    "marked": bool(s.attendance_marked),
                })
        context.sessions = sessions

        # ── Stats ───────────────────────────────────────────────────
        context.total_sessions = len(sessions)
        context.marked_sessions = sum(1 for s in sessions if s["marked"])
        context.pending_sessions = sum(1 for s in sessions if not s["marked"])
        avg_pct = 0.0
        marked = [s["pct"] for s in sessions if s["marked"]]
        if marked:
            avg_pct = round(sum(marked) / len(marked), 1)
        context.avg_attendance_pct = avg_pct

        # ── Condonation requests pending faculty recommendation ─────
        condonation_requests = []
        if co_names:
            raw_cond = frappe.get_all(
                "Student Attendance Condonation",
                filters={
                    "course_offering": ["in", co_names],
                    "final_status": "Pending",
                },
                fields=["name", "student", "course_offering", "number_of_sessions",
                        "number_of_hours", "condonation_reason", "faculty_recommendation",
                        "final_status", "creation"],
                order_by="creation desc",
                ignore_permissions=True,
            )
            for req in raw_cond:
                student_name = frappe.db.get_value(
                    "Student Master", req.student, "first_name"
                ) or req.student
                co = co_map.get(req.course_offering, frappe._dict())
                condonation_requests.append({
                    "name": req.name,
                    "student": req.student,
                    "student_display": student_name,
                    "course_display": co.get("course_name") or req.course_offering,
                    "sessions": req.number_of_sessions or 0,
                    "hours": round(float(req.number_of_hours or 0), 1),
                    "reason": req.condonation_reason or "—",
                    "recommendation": req.faculty_recommendation or "",
                    "status": req.final_status or "Pending",
                    "created": frappe.utils.formatdate(req.creation, "dd MMM yyyy"),
                })
        context.condonation_requests = condonation_requests
        context.pending_condonation = len([r for r in condonation_requests if not r["recommendation"]])

        # ── Monthly summary per course offering ─────────────────────
        monthly_summary = []
        if co_names:
            for co in course_offerings[:6]:
                att_summary = frappe.db.get_value(
                    "Attendance Summary",
                    {"course_offering": co.name},
                    ["total_classes", "attended_classes", "attendance_percentage"],
                    as_dict=True,
                )
                if att_summary:
                    monthly_summary.append({
                        "course_name": co.course_name,
                        "total_classes": att_summary.total_classes or 0,
                        "attended": att_summary.attended_classes or 0,
                        "avg_pct": round(float(att_summary.attendance_percentage or 0), 1),
                    })
        context.monthly_summary = monthly_summary

    except Exception as e:
        frappe.log_error(f"Faculty Portal Attendance error: {e}", "Faculty Portal")
        context.portal_error = str(e)
        set_nav_defaults(context)
        _set_defaults(context)

    return context


def _set_defaults(context):
    context.course_offerings = []
    context.selected_co = ""
    context.sessions = []
    context.total_sessions = 0
    context.marked_sessions = 0
    context.pending_sessions = 0
    context.avg_attendance_pct = 0.0
    context.condonation_requests = []
    context.pending_condonation = 0
    context.monthly_summary = []
