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
        return context

    context.no_student = False

    try:
        student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
        _set_student_nav(context, student)

        # ── Attendance Summaries ───────────────────────────────
        summaries = frappe.get_all(
            "Attendance Summary",
            filters={"student": student_name},
            fields=[
                "name", "course_offering", "course", "department",
                "academic_year", "term_name",
                "total_classes", "attended_classes",
                "total_class_hours", "total_attended_class_hours",
                "total_condonation_hours", "total_fa_mfa_hours",
                "attendance_percentage", "minimum_required_percentage",
                "eligible_for_exam", "last_updated"
            ],
            order_by="term_name desc, course_offering asc",
            ignore_permissions=True
        )

        # Enrich with course name
        for s in summaries:
            co_name = s.course_offering or ""
            s["course_display"] = co_name or s.course or "Unknown Course"
            s["faculty"] = "—"
            if co_name:
                try:
                    co = frappe.db.get_value(
                        "Course Offering", co_name,
                        ["course_name", "faculty", "term_name"],
                        as_dict=True
                    )
                    if co:
                        s["course_display"] = co.course_name or s["course_display"]
                        s["faculty"] = co.faculty or "—"
                        if not s.term_name:
                            s["term_name"] = co.term_name or ""
                except Exception:
                    pass

            pct = s.attendance_percentage or 0
            req = s.minimum_required_percentage or 75
            s["pct"] = round(pct, 1)
            s["status_color"] = "var(--success)" if pct >= 75 else "var(--warning)" if pct >= 60 else "var(--danger)"
            s["status_label"] = "Good" if pct >= 75 else "Low" if pct >= 60 else "Critical"
            s["shortfall"] = max(0, round(req - pct, 1))

        # ── Overall Stats ──────────────────────────────────────
        if summaries:
            pcts = [s.attendance_percentage or 0 for s in summaries]
            context.avg_attendance = round(sum(pcts) / len(pcts), 1)
            context.total_courses = len(summaries)
            context.courses_below_75 = sum(1 for p in pcts if p < 75)
            context.courses_eligible = sum(1 for s in summaries if s.eligible_for_exam)
        else:
            context.avg_attendance = 0.0
            context.total_courses = 0
            context.courses_below_75 = 0
            context.courses_eligible = 0

        context.attendance_summaries = summaries

        # ── Group by term ──────────────────────────────────────
        term_groups = {}
        for s in summaries:
            term = s.term_name or "Other"
            term_groups.setdefault(term, []).append(s)

        context.term_groups = [
            {"term": t, "summaries": v} for t, v in term_groups.items()
        ]

        # ── Recent Daily Attendance (last 30 days) ─────────────
        today = frappe.utils.today()
        from_date = frappe.utils.add_days(today, -30)
        try:
            recent_records = frappe.get_all(
                "Student Attendance",
                filters=[
                    ["student", "=", student_name],
                    ["attendance_date", ">=", from_date],
                    ["attendance_date", "<=", today],
                ],
                fields=["attendance_date", "course_offering", "status", "in_time", "out_time"],
                order_by="attendance_date desc",
                limit=30,
                ignore_permissions=True
            )
            context.recent_attendance = recent_records
        except Exception:
            context.recent_attendance = []

    except Exception as e:
        frappe.log_error(f"Student Portal Attendance error: {e}", "Student Portal")
        context.portal_error = str(e)
        _set_nav_defaults(context)

    return context


def _get_student_name():
    user = frappe.session.user
    name = frappe.db.get_value("Student Master", {"user": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"email": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"official_email_id": user}, "name")
    return name


def _set_student_nav(context, student):
    full_name = " ".join(filter(None, [student.first_name, student.middle_name, student.last_name]))
    context.student_name = full_name or student.name
    context.student_id = student.registration_id or student.name
    context.student_photo = student.passport_size_photo or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    context.programme_name = frappe.db.get_value("Cohort", student.programme, "cohort_name") or student.programme or ""
    context.department = student.department or ""
    context.batch_year = student.batch_year or ""


def _set_nav_defaults(context):
    user = frappe.session.user
    user_doc = frappe.db.get_value("User", user, ["full_name", "user_image"], as_dict=True)
    context.student_name = (user_doc.full_name if user_doc else "") or user.split("@")[0]
    context.student_id = ""
    context.student_photo = (user_doc.user_image if user_doc else "") or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    context.programme_name = ""
    context.department = ""
    context.batch_year = ""
