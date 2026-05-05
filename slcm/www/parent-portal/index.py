import frappe
from slcm.slcm.utils.parent_portal import get_parent_context

no_cache = 1


def get_context(context):
    student = get_parent_context(context)
    if context.is_guest or context.not_a_parent or not student:
        _set_defaults(context)
        return context

    context.active_page = "dashboard"

    # ── Attendance summary ─────────────────────────────────────────
    try:
        summaries = frappe.get_all(
            "Attendance Summary",
            filters={"student": student.name},
            fields=["course", "course_offering", "term_name",
                    "total_classes", "attended_classes",
                    "attendance_percentage", "eligible_for_exam"],
            order_by="term_name desc, course asc",
            ignore_permissions=True,
        )
        # Enrich with course display name from Course Offering
        for s in summaries:
            s["course_name"] = s.course
            if s.course_offering:
                try:
                    cn = frappe.db.get_value("Course Offering", s.course_offering, "course_name")
                    if cn:
                        s["course_name"] = cn
                except Exception:
                    pass
        context.attendance_summaries = summaries
        if summaries:
            percs = [s.attendance_percentage for s in summaries if s.attendance_percentage is not None]
            context.avg_attendance = round(sum(percs) / len(percs), 1) if percs else 0
            context.courses_below_75 = sum(1 for p in percs if p < 75)
            context.course_count = len(summaries)
            context.courses_eligible = sum(1 for s in summaries if s.eligible_for_exam)
        else:
            context.avg_attendance = 0
            context.courses_below_75 = 0
            context.course_count = 0
            context.courses_eligible = 0
    except Exception:
        context.attendance_summaries = []
        context.avg_attendance = 0
        context.courses_below_75 = 0
        context.course_count = 0
        context.courses_eligible = 0

    # ── Latest published result ────────────────────────────────────
    try:
        pub_rows = frappe.get_all(
            "Student Result Publish",
            filters={"student": student.name, "is_published": 1},
            fields=["exam_plan", "published_on"],
            order_by="published_on desc",
            limit=1,
            ignore_permissions=True,
        )
        if pub_rows:
            ep_name = pub_rows[0].exam_plan
            ep_label = frappe.db.get_value("Exam Plan", ep_name, "exam_name") or ep_name
            context.latest_result = {
                "exam_name": ep_label,
                "published_on": pub_rows[0].published_on,
            }
        else:
            context.latest_result = None
    except Exception:
        context.latest_result = None

    # ── Attendance threshold for colour coding ─────────────────────
    try:
        from slcm.slcm.doctype.student_portal_settings.student_portal_settings import get_student_portal_settings
        ps = get_student_portal_settings()
        context.att_good = float(ps.get("att_good_threshold", 75))
        context.att_warn = float(ps.get("att_warn_threshold", 60))
    except Exception:
        context.att_good = 75.0
        context.att_warn = 60.0

    return context


def _set_defaults(context):
    context.attendance_summaries = []
    context.avg_attendance = 0
    context.courses_below_75 = 0
    context.course_count = 0
    context.latest_result = None
    context.att_good = 75.0
    context.att_warn = 60.0
    context.courses_eligible = 0
