import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "courses"

    student_name = _get_student_name()
    if not student_name:
        context.no_student = True
        _set_nav_defaults(context)
        return context

    context.no_student = False

    try:
        student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
        _set_student_nav(context, student)

        # ── All Enrollments ────────────────────────────────────
        enrollments = frappe.get_all(
            "Student Enrollment",
            filters={"student": student_name},
            fields=["name", "cohort", "program", "academic_year", "term_name",
                    "status", "faculty_advisor", "enrollment_date"],
            order_by="creation desc",
            ignore_permissions=True
        )

        # ── Build per-enrollment course lists ──────────────────
        attendance_map = {}
        att_summaries = frappe.get_all(
            "Attendance Summary",
            filters={"student": student_name},
            fields=["course_offering", "course", "attendance_percentage",
                    "total_classes", "attended_classes", "eligible_for_exam"],
            ignore_permissions=True
        )
        for s in att_summaries:
            if s.course_offering:
                attendance_map[s.course_offering] = s
            if s.course:
                attendance_map.setdefault(s.course, s)

        enrollment_data = []
        for enr in enrollments:
            courses_raw = frappe.get_all(
                "Student Enrollment Course",
                filters={"parent": enr.name},
                fields=["course_offering", "course", "credits", "status"],
                ignore_permissions=True
            )

            courses_out = []
            for ec in courses_raw:
                co_name = ec.course_offering or ""
                co_data = {}
                faculty = "—"
                course_display_name = ec.course or co_name or "—"
                credit_value = ec.credits or 0

                if co_name:
                    try:
                        co = frappe.db.get_value(
                            "Course Offering", co_name,
                            ["course_name", "faculty", "credit_value", "status", "term_name"],
                            as_dict=True
                        )
                        if co:
                            co_data = co
                            faculty = co.faculty or "—"
                            course_display_name = co.course_name or course_display_name
                            credit_value = co.credit_value or credit_value
                    except Exception:
                        pass

                att = attendance_map.get(co_name) or attendance_map.get(ec.course) or {}
                att_pct = round(att.get("attendance_percentage") or 0, 1) if att else 0
                eligible = att.get("eligible_for_exam") if att else None

                courses_out.append({
                    "course_offering": co_name,
                    "course": ec.course or "",
                    "course_name": course_display_name,
                    "faculty": faculty,
                    "credits": credit_value,
                    "status": ec.status or "Enrolled",
                    "attendance_pct": att_pct,
                    "eligible_for_exam": eligible,
                    "total_classes": att.get("total_classes") or 0 if att else 0,
                    "attended_classes": att.get("attended_classes") or 0 if att else 0,
                })

            # Sort: active first
            courses_out.sort(key=lambda c: (0 if c["status"] == "Enrolled" else 1, c["course_name"]))

            enrollment_data.append({
                "enrollment": enr,
                "courses": courses_out,
                "course_count": len(courses_out),
                "total_credits": sum(c["credits"] for c in courses_out),
            })

        context.enrollment_data = enrollment_data
        context.has_any_courses = any(ed["course_count"] > 0 for ed in enrollment_data)
        context.active_enrollment = enrollment_data[0] if enrollment_data else None

    except Exception as e:
        frappe.log_error(f"Student Portal Courses error: {e}", "Student Portal")
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
