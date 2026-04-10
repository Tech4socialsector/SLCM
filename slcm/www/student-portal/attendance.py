import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "attendance"

    student_name = _get_student_name()
    if not student_name:
        context.no_student = True
        _set_nav_defaults(context)
        _set_defaults(context)
        return context

    context.no_student = False

    try:
        student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
        _set_student_nav(context, student)

        # ── Attendance Settings ────────────────────────────────────
        try:
            settings = frappe.get_single("Attendance Settings")
            context.allow_fa_mfa = bool(settings.allow_fa_mfa)
            context.allow_condonation = bool(settings.allow_condonation)
            context.min_condonation_pct = float(
                getattr(settings, "condonation_min_percentage", 66) or 66
            )
        except Exception:
            context.allow_fa_mfa = True
            context.allow_condonation = True
            context.min_condonation_pct = 66.0

        # ── Condonation Reasons ────────────────────────────────────
        try:
            context.condonation_reasons = [
                r.name
                for r in frappe.get_all(
                    "Condonation Reason",
                    fields=["name"],
                    order_by="name asc",
                    ignore_permissions=True,
                )
            ]
        except Exception:
            context.condonation_reasons = []

        # ── Attendance Summaries ───────────────────────────────────
        summaries = frappe.get_all(
            "Attendance Summary",
            filters={"student": student_name},
            fields=[
                "name", "course_offering", "course", "department",
                "academic_year", "term_name",
                "total_classes", "attended_classes",
                "total_class_hours", "total_attended_class_hours",
                "total_office_hours", "total_condonation_hours", "total_fa_mfa_hours",
                "attendance_percentage", "minimum_required_percentage",
                "eligible_for_exam", "last_updated",
            ],
            order_by="term_name desc, course_offering asc",
            ignore_permissions=True,
        )

        # Enrich with Course Offering info
        student_courses = []      # for FA/MFA course dropdown (Course link)
        student_cos = []          # for Condonation dropdown (Course Offering link)
        seen_courses = set()
        seen_cos = set()

        for s in summaries:
            co_name = s.course_offering or ""
            s["course_display"] = co_name or s.course or "Unknown Course"
            s["faculty"] = "—"

            if co_name:
                try:
                    co = frappe.db.get_value(
                        "Course Offering",
                        co_name,
                        ["course_name", "faculty", "term_name"],
                        as_dict=True,
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
                "var(--sp-success)" if pct >= 75
                else "var(--sp-warning)" if pct >= 60
                else "var(--sp-danger)"
            )
            s["status_label"] = (
                "Good" if pct >= 75 else "Low" if pct >= 60 else "Critical"
            )
            s["shortfall"] = max(0, round(req - pct, 1))
            s["can_apply_condonation"] = (
                context.allow_condonation
                and pct >= context.min_condonation_pct
                and pct < req
            )

            # Build unique course list for FA/MFA modal
            course_id = s.course or ""
            if course_id and course_id not in seen_courses:
                seen_courses.add(course_id)
                student_courses.append({
                    "course": course_id,
                    "name": s["course_display"],
                })

            # Build unique course-offering list for Condonation modal
            if co_name and co_name not in seen_cos:
                seen_cos.add(co_name)
                student_cos.append({
                    "course_offering": co_name,
                    "name": s["course_display"],
                })

        context.student_courses = student_courses
        context.student_cos = student_cos

        # ── Overall Stats ──────────────────────────────────────────
        if summaries:
            pcts = [float(s.attendance_percentage or 0) for s in summaries]
            context.avg_attendance = round(sum(pcts) / len(pcts), 1)
            context.total_courses = len(summaries)
            context.courses_below_75 = sum(1 for p in pcts if p < 75)
            context.courses_eligible = sum(
                1 for s in summaries if s.eligible_for_exam
            )
        else:
            context.avg_attendance = 0.0
            context.total_courses = 0
            context.courses_below_75 = 0
            context.courses_eligible = 0

        context.attendance_summaries = summaries

        # ── Group by term ──────────────────────────────────────────
        term_groups = {}
        for s in summaries:
            term = s.term_name or "Other"
            term_groups.setdefault(term, []).append(s)

        context.term_groups = [
            {"term": t, "summaries": v} for t, v in term_groups.items()
        ]

        # ── FA/MFA Applications ────────────────────────────────────
        try:
            fa_mfa_apps = frappe.get_all(
                "FA MFA Application",
                filters={"student": student_name},
                fields=[
                    "name", "course", "course_name", "examination_date",
                    "application_type", "reason", "status",
                    "granted_hours", "rejection_reason", "creation",
                ],
                order_by="creation desc",
                ignore_permissions=True,
            )
            for app in fa_mfa_apps:
                st = app.status or "Pending"
                app["status_color"] = {
                    "Pending":  "var(--sp-warning)",
                    "Approved": "var(--sp-success)",
                    "Rejected": "var(--sp-danger)",
                }.get(st, "var(--sp-text-4)")
                app["status_bg"] = {
                    "Pending":  "var(--sp-warning-bg)",
                    "Approved": "var(--sp-success-bg)",
                    "Rejected": "var(--sp-danger-bg)",
                }.get(st, "var(--sp-bg)")
            context.fa_mfa_applications = fa_mfa_apps
        except Exception:
            context.fa_mfa_applications = []

        # ── Condonation Applications ───────────────────────────────
        try:
            cond_apps = frappe.get_all(
                "Student Attendance Condonation",
                filters={"student": student_name},
                fields=[
                    "name", "course_offering", "course", "number_of_sessions",
                    "number_of_hours", "condonation_reason", "final_status",
                    "faculty_recommendation", "remarks", "creation",
                ],
                order_by="creation desc",
                ignore_permissions=True,
            )
            for app in cond_apps:
                st = app.final_status or "Pending"
                app["status_color"] = {
                    "Pending":  "var(--sp-warning)",
                    "Approved": "var(--sp-success)",
                    "Rejected": "var(--sp-danger)",
                }.get(st, "var(--sp-text-4)")
                app["status_bg"] = {
                    "Pending":  "var(--sp-warning-bg)",
                    "Approved": "var(--sp-success-bg)",
                    "Rejected": "var(--sp-danger-bg)",
                }.get(st, "var(--sp-bg)")
                # Resolve course display name from summaries
                app["course_display"] = app.course_offering or app.course or "—"
                for s in summaries:
                    if s.course_offering == app.course_offering:
                        app["course_display"] = s.get("course_display") or app["course_display"]
                        break
            context.condonation_applications = cond_apps
        except Exception:
            context.condonation_applications = []

        # ── Office Hours Sessions ──────────────────────────────────
        try:
            enrolled_cos = [s.course_offering for s in summaries if s.course_offering]
            if enrolled_cos:
                today_date = frappe.utils.today()
                office_hours = frappe.get_all(
                    "Office Hours Session",
                    filters=[
                        ["course_offering", "in", enrolled_cos],
                        ["session_date", ">=", today_date],
                        ["session_status", "in", ["Scheduled", "Conducted"]],
                    ],
                    fields=[
                        "name", "course_offering", "course", "faculty",
                        "session_date", "start_time", "end_time",
                        "duration_hours", "location", "session_status",
                    ],
                    order_by="session_date asc, start_time asc",
                    limit=30,
                    ignore_permissions=True,
                )
                for oh in office_hours:
                    oh["course_display"] = oh.course_offering or "—"
                    for s in summaries:
                        if s.course_offering == oh.course_offering:
                            oh["course_display"] = s.get("course_display") or oh["course_display"]
                            break
                    oh["start_fmt"] = _fmt_time(oh.start_time)
                    oh["end_fmt"] = _fmt_time(oh.end_time)
                    oh["is_scheduled"] = oh.session_status == "Scheduled"
                context.office_hours_sessions = office_hours
            else:
                context.office_hours_sessions = []
        except Exception:
            context.office_hours_sessions = []

        # ── Recent Daily Attendance (last 30 days) ─────────────────
        today_date = frappe.utils.today()
        from_date = frappe.utils.add_days(today_date, -30)
        try:
            recent_records = frappe.get_all(
                "Student Attendance",
                filters=[
                    ["student", "=", student_name],
                    ["attendance_date", ">=", from_date],
                    ["attendance_date", "<=", today_date],
                ],
                fields=[
                    "attendance_date", "course_offer", "status",
                    "in_time", "out_time", "session_type",
                ],
                order_by="attendance_date desc",
                limit=30,
                ignore_permissions=True,
            )
            context.recent_attendance = recent_records
        except Exception:
            context.recent_attendance = []

    except Exception as e:
        frappe.log_error(f"Student Portal Attendance error: {e}", "Student Portal")
        context.portal_error = str(e)
        _set_nav_defaults(context)
        _set_defaults(context)

    return context


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_student_name():
    user = frappe.session.user
    name = frappe.db.get_value("Student Master", {"user": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"email": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"official_email_id": user}, "name")
    return name


def _fmt_time(t):
    """Convert a time value to a readable 12-hour format string."""
    if not t:
        return "—"
    try:
        parts = str(t).split(":")
        h = int(parts[0])
        m = parts[1] if len(parts) > 1 else "00"
        ampm = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m} {ampm}"
    except Exception:
        return str(t)


def _set_defaults(context):
    context.allow_fa_mfa = True
    context.allow_condonation = True
    context.min_condonation_pct = 66.0
    context.condonation_reasons = []
    context.student_courses = []
    context.student_cos = []
    context.attendance_summaries = []
    context.term_groups = []
    context.fa_mfa_applications = []
    context.condonation_applications = []
    context.office_hours_sessions = []
    context.recent_attendance = []
    context.avg_attendance = 0.0
    context.total_courses = 0
    context.courses_below_75 = 0
    context.courses_eligible = 0


def _set_student_nav(context, student):
    full_name = " ".join(
        filter(None, [student.first_name, student.middle_name, student.last_name])
    )
    context.student_name = full_name or student.name
    context.student_id = student.registration_id or student.name
    context.student_photo = student.passport_size_photo or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    context.programme_name = (
        frappe.db.get_value("Cohort", student.programme, "cohort_name")
        or student.programme
        or ""
    )
    context.department = student.department or ""
    context.batch_year = student.batch_year or ""


def _set_nav_defaults(context):
    user = frappe.session.user
    user_doc = frappe.db.get_value(
        "User", user, ["full_name", "user_image"], as_dict=True
    )
    context.student_name = (user_doc.full_name if user_doc else "") or user.split("@")[0]
    context.student_id = ""
    context.student_photo = (user_doc.user_image if user_doc else "") or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    context.programme_name = ""
    context.department = ""
    context.batch_year = ""
