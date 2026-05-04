import frappe
from slcm.slcm.utils.parent_portal import get_parent_context

no_cache = 1


def get_context(context):
    student = get_parent_context(context)
    if context.is_guest or context.not_a_parent or not student:
        _set_defaults(context)
        return context

    context.active_page = "attendance"

    # ── Colour thresholds ──────────────────────────────────────────
    try:
        from slcm.slcm.doctype.student_portal_settings.student_portal_settings import get_student_portal_settings
        ps = get_student_portal_settings()
        context.att_good = float(ps.get("att_good_threshold", 75))
        context.att_warn = float(ps.get("att_warn_threshold", 60))
        context.att_label_good   = ps.get("att_label_good",   "Good")
        context.att_label_warn   = ps.get("att_label_warn",   "Low")
        context.att_label_danger = ps.get("att_label_danger", "Critical")
    except Exception:
        context.att_good = 75.0
        context.att_warn = 60.0
        context.att_label_good   = "Good"
        context.att_label_warn   = "Low"
        context.att_label_danger = "Critical"

    # ── Attendance Summaries ───────────────────────────────────────
    summaries = frappe.get_all(
        "Attendance Summary",
        filters={"student": student.name},
        fields=[
            "name", "course_offering", "course", "department",
            "academic_year", "term_name",
            "total_classes", "attended_classes",
            "total_class_hours", "total_attended_class_hours",
            "attendance_percentage", "minimum_required_percentage",
            "eligible_for_exam", "last_updated",
        ],
        order_by="term_name desc, course_offering asc",
        ignore_permissions=True,
    )

    for s in summaries:
        co_name = s.course_offering or ""
        s["course_display"] = co_name or s.course or "Unknown"
        s["faculty"] = "—"
        if co_name:
            try:
                co = frappe.db.get_value(
                    "Course Offering", co_name,
                    ["course_name", "faculty", "term_name"], as_dict=True,
                )
                if co:
                    s["course_display"] = co.course_name or s["course_display"]
                    s["faculty"] = co.faculty or "—"
                    if not s.term_name:
                        s["term_name"] = co.term_name or ""
            except Exception:
                pass

        pct = float(s.attendance_percentage or 0)
        req = float(s.minimum_required_percentage or 75)
        s["pct"] = round(pct, 1)
        s["status_color"] = (
            "var(--pp-success)" if pct >= context.att_good
            else "var(--pp-warning)" if pct >= context.att_warn
            else "var(--pp-danger)"
        )
        s["status_label"] = (
            context.att_label_good if pct >= context.att_good
            else context.att_label_warn if pct >= context.att_warn
            else context.att_label_danger
        )
        s["status_bg"] = (
            "var(--pp-success-bg)" if pct >= context.att_good
            else "var(--pp-warning-bg)" if pct >= context.att_warn
            else "var(--pp-danger-bg)"
        )
        s["shortfall"] = max(0, round(req - pct, 1))

    context.attendance_summaries = summaries

    # ── Overall stats ──────────────────────────────────────────────
    if summaries:
        pcts = [float(s.attendance_percentage or 0) for s in summaries]
        context.avg_attendance = round(sum(pcts) / len(pcts), 1)
        context.total_courses = len(summaries)
        context.courses_below_75 = sum(1 for p in pcts if p < context.att_good)
        context.courses_eligible = sum(1 for s in summaries if s.eligible_for_exam)
    else:
        context.avg_attendance = 0.0
        context.total_courses = 0
        context.courses_below_75 = 0
        context.courses_eligible = 0

    # ── Group by term ──────────────────────────────────────────────
    term_groups = {}
    for s in summaries:
        term = s.term_name or "Other"
        term_groups.setdefault(term, []).append(s)
    context.term_groups = [{"term": t, "summaries": v} for t, v in term_groups.items()]

    # ── Recent daily attendance (last 30 days) ─────────────────────
    today_date = frappe.utils.today()
    from_date = frappe.utils.add_days(today_date, -30)
    try:
        recent = frappe.get_all(
            "Student Attendance",
            filters=[
                ["student", "=", student.name],
                ["attendance_date", ">=", from_date],
                ["attendance_date", "<=", today_date],
            ],
            fields=["attendance_date", "course_offer", "status", "session_type"],
            order_by="attendance_date desc",
            limit=60,
            ignore_permissions=True,
        )
        # Resolve course display name
        co_map = {s.course_offering: s.get("course_display") for s in summaries if s.course_offering}
        for r in recent:
            r["course_display"] = co_map.get(r.course_offer) or r.course_offer or "—"
        context.recent_attendance = recent
    except Exception:
        context.recent_attendance = []

    return context


def _set_defaults(context):
    context.attendance_summaries = []
    context.avg_attendance = 0.0
    context.total_courses = 0
    context.courses_below_75 = 0
    context.courses_eligible = 0
    context.term_groups = []
    context.recent_attendance = []
    context.att_good = 75.0
    context.att_warn = 60.0
    context.att_label_good   = "Good"
    context.att_label_warn   = "Low"
    context.att_label_danger = "Critical"
