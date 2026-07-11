import frappe
from slcm.slcm.utils.parent_portal import get_parent_context

no_cache = 1


def get_context(context):
    student = get_parent_context(context)
    if context.is_guest or context.not_a_parent or not student:
        _set_defaults(context)
        return context

    context.active_page = "dashboard"

    ps = context.pp_settings or {}
    context.att_good = float(ps.get("att_good_threshold", 75))
    context.att_warn = float(ps.get("att_warn_threshold", 60))

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
            context.avg_attendance    = round(sum(percs) / len(percs), 1) if percs else 0
            context.courses_below_75  = sum(1 for p in percs if p < context.att_good)
            context.course_count      = len(summaries)
            context.courses_eligible  = sum(1 for s in summaries if s.eligible_for_exam)
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
            ep_name  = pub_rows[0].exam_plan
            ep_label = frappe.db.get_value("Exam Plan", ep_name, "exam_name") or ep_name
            context.latest_result = {
                "exam_name":    ep_label,
                "published_on": pub_rows[0].published_on,
            }
        else:
            context.latest_result = None
    except Exception:
        context.latest_result = None

    # ── Hostel details ─────────────────────────────────────────────
    try:
        context.is_hosteller = bool(student.is_hosteller)
        if context.is_hosteller:
            hostel_name = ""
            if student.hostel:
                hostel_name = frappe.db.get_value("Hostel", student.hostel, "hostel_name") or student.hostel
            room_number = ""
            if student.hostel_room:
                room_number = frappe.db.get_value("Hostel Room", student.hostel_room, "room_number") or student.hostel_room
            bed_no = ""
            if student.hostel_bed:
                bed_no = frappe.db.get_value("Hostel Bed", student.hostel_bed, "bed_no") or student.hostel_bed
            context.hostel_details = {
                "hostel_name":    hostel_name,
                "hostel_block":   student.hostel_block or "",
                "room_number":    room_number,
                "bed_no":         bed_no,
                "hostel_status":  student.hostel_status or "",
                "meal_plan":      student.meal_plan or "",
                "key_number":     student.key_number or "",
                "allocation_date": frappe.utils.formatdate(student.allocation_date, "dd MMM yyyy") if student.allocation_date else "",
            }
        else:
            context.hostel_details = None
    except Exception:
        context.is_hosteller = False
        context.hostel_details = None

    # ── Academic profile ───────────────────────────────────────────
    context.ward_enrolment_no = getattr(student, "enrolment_number", "") or getattr(student, "student_id", "") or student.name
    context.ward_section      = getattr(student, "section", "") or ""
    context.ward_email        = getattr(student, "student_email_id", "") or ""

    # ── RFID In/Out — last 10 swipes ──────────────────────────────
    try:
        logs = frappe.get_all(
            "Attendance Log",
            filters={"student": student.name},
            fields=["swipe_time", "location", "terminal_alias", "source"],
            order_by="swipe_time desc",
            limit=10,
            ignore_permissions=True,
        )
        for lg in logs:
            if lg.swipe_time:
                lg["swipe_time_fmt"] = frappe.utils.format_datetime(lg.swipe_time, "dd MMM yyyy, hh:mm a")
                lg["swipe_date"]     = frappe.utils.formatdate(lg.swipe_time, "dd MMM yyyy")
                lg["swipe_clock"]    = frappe.utils.format_datetime(lg.swipe_time, "hh:mm a")
            else:
                lg["swipe_time_fmt"] = "—"
                lg["swipe_date"]     = "—"
                lg["swipe_clock"]    = "—"
        context.rfid_logs = logs
    except Exception:
        context.rfid_logs = []

    # ── Time Table — today + next 7 days ──────────────────────
    try:
        today    = frappe.utils.today()
        end_date = frappe.utils.add_days(today, 7)

        # Get active course offerings for this student
        active_offerings = [s.course_offering for s in context.attendance_summaries if s.course_offering]

        schedules = []
        if active_offerings:
            schedules = frappe.get_all(
                "Time Table",
                filters={
                    "schedule_date": ["between", [today, end_date]],
                    "course_offering": ["in", active_offerings],
                    "status": ["!=", "Cancelled"],
                },
                fields=["name", "course", "course_offering", "instructor",
                        "schedule_date", "from_time", "to_time",
                        "venue", "duration_hours", "status"],
                order_by="schedule_date asc, from_time asc",
                limit=15,
                ignore_permissions=True,
            )

        for sc in schedules:
            # Course display name
            sc["course_name"] = sc.course or "—"
            if sc.course_offering:
                try:
                    cn = frappe.db.get_value("Course Offering", sc.course_offering, "course_name")
                    if cn:
                        sc["course_name"] = cn
                except Exception:
                    pass
            # Friendly date label
            sd = sc.schedule_date
            if sd:
                if str(sd) == today:
                    sc["date_label"] = "Today"
                elif str(sd) == frappe.utils.add_days(today, 1):
                    sc["date_label"] = "Tomorrow"
                else:
                    sc["date_label"] = frappe.utils.formatdate(sd, "EEE, dd MMM")
                sc["date_fmt"] = frappe.utils.formatdate(sd, "dd MMM")
                sc["is_today"] = str(sd) == today
            else:
                sc["date_label"] = "—"
                sc["date_fmt"]   = "—"
                sc["is_today"]   = False
            # Format times
            sc["from_time_fmt"] = _fmt_time(sc.from_time)
            sc["to_time_fmt"]   = _fmt_time(sc.to_time)

        context.class_schedules = schedules
    except Exception:
        context.class_schedules = []

    return context


def _fmt_time(t):
    if not t:
        return ""
    try:
        from datetime import time as dtime
        if isinstance(t, dtime):
            h, m = t.hour, t.minute
        else:
            parts = str(t).split(":")
            h, m  = int(parts[0]), int(parts[1])
        ampm = "AM" if h < 12 else "PM"
        h12  = h % 12 or 12
        return f"{h12}:{m:02d} {ampm}"
    except Exception:
        return str(t)


def _set_defaults(context):
    context.attendance_summaries = []
    context.avg_attendance       = 0
    context.courses_below_75     = 0
    context.course_count         = 0
    context.latest_result        = None
    context.att_good             = 75.0
    context.att_warn             = 60.0
    context.courses_eligible     = 0
    context.is_hosteller         = False
    context.hostel_details       = None
    context.rfid_logs            = []
    context.class_schedules      = []
    context.ward_enrolment_no    = ""
    context.ward_section         = ""
    context.ward_email           = ""
    if not getattr(context, "pp_settings", None):
        from slcm.slcm.doctype.parent_portal_settings.parent_portal_settings import get_parent_portal_settings
        try:
            context.pp_settings = get_parent_portal_settings()
        except Exception:
            context.pp_settings = {}
