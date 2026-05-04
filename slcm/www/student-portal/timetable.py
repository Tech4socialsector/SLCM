import frappe
from datetime import timedelta

no_cache = 1

# Palette – one colour per enrolled course_offering (cycles if > 10)
_PALETTE = [
    "#c84630", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6",
    "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
]


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest    = False
    context.active_page = "timetable"

    student_name = _get_student_name()
    if not student_name:
        context.no_student = True
        _set_nav_defaults(context)
        return context

    context.no_student = False

    try:
        student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
        _set_student_nav(context, student)

        # ── Week navigation ───────────────────────────────────────
        today      = frappe.utils.getdate()
        week_param = frappe.local.form_dict.get("week", "")
        if week_param:
            try:
                raw = frappe.utils.getdate(week_param)
                week_start = raw - timedelta(days=raw.weekday())
            except Exception:
                week_start = today - timedelta(days=today.weekday())
        else:
            week_start = today - timedelta(days=today.weekday())

        week_end              = week_start + timedelta(days=5)   # Saturday
        context.week_start    = week_start
        context.week_end      = week_end
        context.today         = today
        context.prev_week     = str(week_start - timedelta(days=7))
        context.next_week     = str(week_start + timedelta(days=7))
        context.is_current_week = (week_start <= today <= week_end)
        context.week_label    = (
            f"{week_start.strftime('%d %b')} – {week_end.strftime('%d %b %Y')}"
        )

        # ── Enrolled course offerings ─────────────────────────────
        att_summaries = frappe.get_all(
            "Attendance Summary",
            filters={"student": student_name},
            fields=["course_offering", "course"],
            ignore_permissions=True,
        )
        enrolled_co_set = {s.course_offering for s in att_summaries if s.course_offering}

        # Build colour map (stable order → stable colours)
        color_map = {}
        for i, co in enumerate(sorted(enrolled_co_set)):
            color_map[co] = _PALETTE[i % len(_PALETTE)]

        # ── Fetch Class Schedules for the week ────────────────────
        raw_schedules = []
        if enrolled_co_set:
            raw_schedules = frappe.get_all(
                "Class Schedule",
                filters=[
                    ["course_offering", "in", list(enrolled_co_set)],
                    ["schedule_date", "between", [str(week_start), str(week_end)]],
                ],
                fields=["name", "course", "course_offering", "instructor",
                        "schedule_date", "from_time", "to_time", "duration_hours",
                        "venue", "title", "color"],
                order_by="schedule_date asc, from_time asc",
                ignore_permissions=True,
            )

            # ── Also handle weekly-repeating parent schedules ─────
            try:
                recurring = frappe.get_all(
                    "Class Schedule",
                    filters=[
                        ["course_offering", "in", list(enrolled_co_set)],
                        ["repeat_frequency", "=", "Weekly"],
                        ["schedule_date", "<=", str(week_end)],
                        ["parent_schedule", "is", "not set"],
                    ],
                    fields=["name", "course", "course_offering", "instructor",
                            "schedule_date", "from_time", "to_time", "duration_hours",
                            "venue", "title", "color", "repeats_till"],
                    ignore_permissions=True,
                )
                for r in recurring:
                    orig      = frappe.utils.getdate(r.schedule_date)
                    proj_date = week_start + timedelta(days=orig.weekday())
                    if not (week_start <= proj_date <= week_end):
                        continue
                    till = frappe.utils.getdate(r.repeats_till) if r.repeats_till else None
                    if till and proj_date > till:
                        continue
                    # Skip if a direct schedule already covers this slot
                    already = any(
                        frappe.utils.getdate(s.schedule_date) == proj_date
                        and s.course_offering == r.course_offering
                        and str(s.from_time) == str(r.from_time)
                        for s in raw_schedules
                    )
                    if not already:
                        copy = frappe._dict(r)
                        copy.schedule_date = proj_date
                        raw_schedules.append(copy)
            except Exception:
                pass

        # ── Enrich with course display names ──────────────────────
        co_names = {s.course_offering for s in raw_schedules if s.course_offering}
        co_info_map = {}
        if co_names:
            rows = frappe.get_all(
                "Course Offering",
                filters={"name": ["in", list(co_names)]},
                fields=["name", "course_name", "faculty"],
                ignore_permissions=True,
            )
            co_info_map = {r.name: r for r in rows}

        # ── Group by day ──────────────────────────────────────────
        days = _build_days(week_start)
        schedules_by_day = {d["date"]: [] for d in days}

        for s in raw_schedules:
            d     = frappe.utils.getdate(s.schedule_date)
            d_str = str(d)
            if d_str not in schedules_by_day:
                continue
            co   = co_info_map.get(s.course_offering, frappe._dict())
            name = (
                co.get("course_name")
                or s.get("title")
                or s.course
                or s.course_offering
                or "—"
            )
            schedules_by_day[d_str].append({
                "name":           s.name,
                "course_offering": s.course_offering or "",
                "course_name":    name,
                "instructor":     co.get("faculty") or s.instructor or "—",
                "from_time":      _fmt_time(s.from_time),
                "to_time":        _fmt_time(s.to_time),
                "venue":          s.venue or "—",
                "color":          color_map.get(s.course_offering) or s.color or _PALETTE[0],
            })

        context.days             = days
        context.schedules_by_day = schedules_by_day
        context.color_map        = color_map
        context.total_this_week  = sum(len(v) for v in schedules_by_day.values())
        context.today_count      = len(schedules_by_day.get(str(today), []))

        # ── Unique course list (for legend) ───────────────────────
        seen   = set()
        legend = []
        for day in days:
            for cls in schedules_by_day.get(day["date"], []):
                co = cls["course_offering"]
                if co not in seen:
                    seen.add(co)
                    legend.append({
                        "course_offering": co,
                        "course_name":     cls["course_name"],
                        "color":           cls["color"],
                    })
        context.legend = legend

    except Exception as exc:
        frappe.log_error(f"Timetable error: {exc}", "Student Portal Timetable")
        context.portal_error = str(exc)
        _set_nav_defaults(context)

    return context


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_days(week_start):
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    days  = []
    for i, name in enumerate(names):
        d = week_start + timedelta(days=i)
        days.append({
            "date":  str(d),
            "label": name,
            "short": name[:3].upper(),
            "num":   d.day,
            "month": d.strftime("%b"),
        })
    return days


def _fmt_time(t):
    """Return '9:30 AM' style string from a time/timedelta value."""
    if t is None:
        return ""
    if hasattr(t, "seconds"):          # timedelta (Frappe stores Time as timedelta)
        total = int(t.seconds)
        h, rem = divmod(total, 3600)
        m      = rem // 60
    elif isinstance(t, str):
        parts  = t.split(":")
        h, m   = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    else:
        return str(t)
    suffix = "AM" if h < 12 else "PM"
    h12    = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


def _get_student_name():
    user = frappe.session.user
    name = frappe.db.get_value("Student Master", {"user": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"email": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"official_email_id": user}, "name")
    return name


def _set_student_nav(context, student):
    full = " ".join(filter(None, [student.first_name, student.middle_name, student.last_name]))
    context.student_name    = full or student.name
    context.student_id      = student.registration_id or student.name
    context.student_photo   = student.passport_size_photo or ""
    context.student_initial = context.student_name[0].upper() if context.student_name else "S"
    context.programme_name  = (
        frappe.db.get_value("Cohort", student.programme, "cohort_name")
        or student.programme or ""
    )
    context.department = student.department or ""
    context.batch_year = student.batch_year or ""


def _set_nav_defaults(context):
    user     = frappe.session.user
    user_doc = frappe.db.get_value("User", user, ["full_name", "user_image"], as_dict=True)
    context.student_name    = (user_doc.full_name if user_doc else "") or user.split("@")[0]
    context.student_id      = ""
    context.student_photo   = (user_doc.user_image if user_doc else "") or ""
    context.student_initial = context.student_name[0].upper() if context.student_name else "S"
    context.programme_name  = ""
    context.department      = ""
    context.batch_year      = ""
