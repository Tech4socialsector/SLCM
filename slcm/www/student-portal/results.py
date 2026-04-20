import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "results"

    student_name = _get_student_name()
    if not student_name:
        context.no_student = True
        _set_nav_defaults(context)
        context.published_results = []
        return context

    context.no_student = False

    try:
        student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
        _set_student_nav(context, student)

        # ── Only show exam plans where this student's result is published ──
        publish_records = frappe.get_all(
            "Student Result Publish",
            filters={"student": student_name, "is_published": 1},
            fields=[
                "name", "exam_plan",
                "term_gpa", "term_percentage",
                "cumulative_gpa", "cumulative_percentage",
                "published_on",
            ],
            ignore_permissions=True,
        )

        published_results = []

        for rec in publish_records:
            ep_name = rec.exam_plan

            # ── Exam Plan label ────────────────────────────────────
            ep = frappe.db.get_value(
                "Exam Plan", ep_name,
                ["exam_name", "term", "status"],
                as_dict=True,
            ) or frappe._dict()

            # ── Publish Result Setting ─────────────────────────────
            setting       = _get_publish_setting(ep_name)
            show_total    = bool(setting and setting.show_total_marks)
            show_sgpa     = bool(setting and setting.show_sgpa)
            hide_sgpa_fail = bool(setting and setting.hide_sgpa_for_failed)

            # Components the admin has whitelisted (empty set = show all)
            allowed_components = set()
            if setting and setting.publish_components:
                for pc in setting.publish_components:
                    if pc.component:
                        allowed_components.add(pc.component)

            # ── Course Marks — NO status filter; is_published is the gate ──
            marks_records = frappe.get_all(
                "Student Course Marks",
                filters={"student": student_name, "exam_plan": ep_name},
                fields=[
                    "name", "course", "evaluation_schema",
                    "total_marks", "grade", "moderated_grade",
                    "updated_final_marks", "updated_grade",
                    "enrollment_status", "attendance_status",
                    "mfa", "remark",
                    # fairness_status intentionally excluded — internal field
                ],
                ignore_permissions=True,
            )

            courses_out  = []
            has_any_fail = False

            for m in marks_records:
                course_name = (
                    frappe.db.get_value("Course", m.course, "course_name") or m.course
                )

                # ── Fetch component marks (always, for display) ────
                comp_marks = _get_component_marks(m.name, allowed_components)

                # ── Effective total marks ──────────────────────────
                # Use updated_final_marks → total_marks → sum of components
                raw_total = (
                    m.updated_final_marks
                    or m.total_marks
                    or (sum(e["marks"] for e in comp_marks) if comp_marks else 0)
                )
                display_total = round(float(raw_total), 2) if raw_total else None

                # ── Effective grade: updated > moderated > raw ─────
                display_grade = (
                    m.updated_grade or m.moderated_grade or m.grade or ""
                )

                # ── Pass / Fail ────────────────────────────────────
                if display_grade:
                    is_fail = _is_failing_grade(display_grade, ep_name, m.course)
                    overall_status = "Fail" if is_fail else "Pass"
                    if is_fail:
                        has_any_fail = True
                else:
                    is_fail       = False
                    overall_status = ""   # grade not assigned yet

                # ── Attendance status with fallback ───────────────
                att_status = m.attendance_status or ""
                if not att_status:
                    att_status = _get_attendance_fallback(student_name, m.course, ep_name)

                # ── Enrollment status with fallback ───────────────
                enroll_status = m.enrollment_status or ""
                if not enroll_status:
                    enroll_status = _get_enrollment_fallback(student_name, m.course)

                courses_out.append({
                    "course":            m.course,
                    "course_name":       course_name,
                    # Grade display
                    "display_grade":     display_grade,      # empty string if not assigned
                    "display_total":     display_total,      # None if no marks at all
                    "overall_status":    overall_status,     # "Pass" | "Fail" | ""
                    "is_fail":           is_fail,
                    # Status fields (may be empty strings)
                    "enrollment_status": enroll_status,
                    "attendance_status": att_status,
                    "mfa":               m.mfa or "",
                    "remark":            m.remark or "",
                    # Component marks
                    "comp_marks":        comp_marks,
                    "has_comp_marks":    bool(comp_marks),
                    # Display flags
                    "show_total":        show_total,
                })

            courses_out.sort(key=lambda c: c["course_name"])

            # ── Summary counts ─────────────────────────────────────
            pass_count    = sum(1 for c in courses_out if c["overall_status"] == "Pass")
            fail_count    = sum(1 for c in courses_out if c["overall_status"] == "Fail")
            pending_count = sum(1 for c in courses_out if c["overall_status"] == "")

            # ── Term GPA / % with admin visibility rules ───────────
            term_gpa = round(float(rec.term_gpa), 2)   if rec.term_gpa         else None
            term_pct = round(float(rec.term_percentage), 2) if rec.term_percentage else None
            cgpa     = round(float(rec.cumulative_gpa), 2)  if rec.cumulative_gpa  else None
            cpct     = round(float(rec.cumulative_percentage), 2) if rec.cumulative_percentage else None

            if show_sgpa and hide_sgpa_fail and has_any_fail:
                term_gpa = None
                term_pct = None

            published_results.append({
                "exam_plan":             ep_name,
                "exam_name":             ep.exam_name or ep_name,
                "term":                  ep.term or "",
                "published_on":          rec.published_on,
                "term_gpa":              term_gpa,
                "term_percentage":       term_pct,
                "cumulative_gpa":        cgpa,
                "cumulative_percentage": cpct,
                "courses":               courses_out,
                "has_any_fail":          has_any_fail,
                "show_sgpa":             show_sgpa,
                "show_total":            show_total,
                "show_cumulative":       bool(cgpa or cpct),
                "pass_count":            pass_count,
                "fail_count":            fail_count,
                "pending_count":         pending_count,
            })

        # Most recently published first
        published_results.sort(
            key=lambda r: str(r["published_on"] or ""), reverse=True
        )

        context.published_results = published_results
        context.has_results = bool(published_results)

    except Exception as e:
        frappe.log_error(f"Student Portal Results error: {e}", "Student Portal")
        context.portal_error = str(e)
        _set_nav_defaults(context)
        context.published_results = []
        context.has_results = False

    return context


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_attendance_fallback(student_name, course, exam_plan):
    """
    Derive attendance status from Attendance Summary when Student Course Marks
    has an empty attendance_status (common for freshly imported records).
    Returns 'Present', 'Low Attendance', 'Detained', or '' if not found.
    """
    try:
        row = frappe.db.get_value(
            "Attendance Summary",
            {"student": student_name, "course": course},
            ["attendance_percentage", "student_status"],
            as_dict=True,
        )
        if not row:
            # Try with exam_plan filter as well
            row = frappe.db.get_value(
                "Attendance Summary",
                {"student": student_name, "course": course, "exam_plan": exam_plan},
                ["attendance_percentage", "student_status"],
                as_dict=True,
            )
        if row:
            # Prefer explicit student_status if present
            if row.get("student_status"):
                return row.student_status
            pct = float(row.attendance_percentage or 0)
            if pct >= 75:
                return "Present"
            elif pct >= 50:
                return "Low Attendance"
            else:
                return "Detained"
    except Exception:
        pass
    return ""


def _get_enrollment_fallback(student_name, course):
    """
    Derive enrollment status from Student Enrollment when Student Course Marks
    has an empty enrollment_status (common for freshly imported records).
    Returns 'Enrolled', 'Detained', 'Dropped', or '' if not found.
    """
    try:
        # Try Student Enrollment child record first
        row = frappe.db.get_value(
            "Student Enrollment",
            {"student": student_name, "course": course},
            ["status", "enrollment_status"],
            as_dict=True,
        )
        if row:
            status = row.get("status") or row.get("enrollment_status") or ""
            if status:
                return status
            return "Enrolled"   # record exists → considered enrolled
    except Exception:
        pass
    return ""


def _get_publish_setting(exam_plan):
    try:
        return frappe.get_doc(
            "Publish Result Setting", exam_plan, ignore_permissions=True
        )
    except Exception:
        return None


def _is_failing_grade(grade, exam_plan=None, course=None):
    """True when grade is a failing grade per Grading Schema, with heuristic fallback."""
    if not grade:
        return False
    # Schema-based lookup via Course Schema Assignment
    if exam_plan and course:
        try:
            grading_schema = frappe.db.get_value(
                "Course Schema Assignment",
                {"exam_plan": exam_plan, "course": course},
                "grade_schema",
            )
            if grading_schema:
                failed = frappe.get_all(
                    "Grading Schema Component",
                    filters={"parent": grading_schema, "failed": 1},
                    pluck="grade",
                    ignore_permissions=True,
                )
                if failed:
                    return grade in set(failed)
        except Exception:
            pass
    # Heuristic fallback
    return grade.upper() in {"F", "FF", "FAIL", "AB", "I", "W", "U", "E"}


def _get_component_marks(marks_doc_name, allowed_components):
    """
    Return list of {label, marks} for Student Marks Entry child rows.
    Filtered to allowed_components if configured; skip rows with marks == 0.
    """
    try:
        entries = frappe.get_all(
            "Student Marks Entry",
            filters={"parent": marks_doc_name},
            fields=["component", "label", "marks", "revaluation_marks", "moderated_marks"],
            ignore_permissions=True,
        )
        out = []
        for e in entries:
            if allowed_components and e.component not in allowed_components:
                continue
            eff = e.moderated_marks or e.revaluation_marks or e.marks or 0
            out.append({
                "label": e.label or e.component or "—",
                "marks": round(float(eff), 2),
            })
        return out
    except Exception:
        return []


# ── Nav helpers ───────────────────────────────────────────────────────────────

def _get_student_name():
    user = frappe.session.user
    name = frappe.db.get_value("Student Master", {"user": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"email": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"official_email_id": user}, "name")
    return name


def _set_student_nav(context, student):
    full_name = " ".join(
        filter(None, [student.first_name, student.middle_name, student.last_name])
    )
    context.student_name    = full_name or student.name
    context.student_id      = student.registration_id or student.name
    context.student_photo   = student.passport_size_photo or ""
    context.student_initial = (
        context.student_name[0].upper() if context.student_name else "S"
    )
    context.programme_name = (
        frappe.db.get_value("Cohort", student.programme, "cohort_name")
        or student.programme or ""
    )
    context.department = student.department or ""
    context.batch_year = student.batch_year or ""


def _set_nav_defaults(context):
    user     = frappe.session.user
    user_doc = frappe.db.get_value(
        "User", user, ["full_name", "user_image"], as_dict=True
    )
    context.student_name    = (user_doc.full_name if user_doc else "") or user.split("@")[0]
    context.student_id      = ""
    context.student_photo   = (user_doc.user_image if user_doc else "") or ""
    context.student_initial = (
        context.student_name[0].upper() if context.student_name else "S"
    )
    context.programme_name = ""
    context.department     = ""
    context.batch_year     = ""
