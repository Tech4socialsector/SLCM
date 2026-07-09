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
        student = frappe.get_doc("Student Master", student_name)
        _set_student_nav(context, student)

        # ── Pre-fetch attendance summaries for fast lookup ─────────
        att_map = {}  # keyed by course_offering and by course
        for s in frappe.get_all(
            "Attendance Summary",
            filters={"student": student_name},
            fields=[
                "course_offering", "course", "attendance_percentage",
                "total_class_hours", "attended_classes",
                "total_classes", "eligible_for_exam",
            ],
            ignore_permissions=True,
        ):
            if s.course_offering:
                att_map[s.course_offering] = s
            if s.course:
                att_map.setdefault(s.course, s)

        # ── All Enrollments ────────────────────────────────────────
        enrollments = frappe.get_all(
            "Student Enrollment",
            filters={"student": student_name},
            fields=[
                "name", "batch", "program", "academic_year",
                "term_name", "status", "faculty_advisor", "enrollment_date",
            ],
            order_by="creation desc",
            ignore_permissions=True,
        )

        # If no formal enrollment record, synthesise one from the student's cohort
        if not enrollments and student.programme:
            cohort_doc = frappe.db.get_value(
                "Batch",
                student.programme,
                ["name", "cohort_name", "academic_year", "term_name", "status"],
                as_dict=True,
            )
            if cohort_doc:
                enrollments = [frappe._dict({
                    "name": None,
                    "batch": cohort_doc.name,
                    "program": None,
                    "academic_year": cohort_doc.academic_year,
                    "term_name": cohort_doc.term_name,
                    "status": "Enrolled",
                    "faculty_advisor": None,
                    "enrollment_date": None,
                })]

        enrollment_data = []

        for enr in enrollments:
            cohort = enr.batch

            # ── Step 1: courses from Student Enrollment Course child table ──
            child_courses = []
            if enr.name:
                child_courses = frappe.get_all(
                    "Student Enrollment Course",
                    filters={"parent": enr.name},
                    fields=["course_offering", "course", "credits", "course_type", "status", "grade"],
                    ignore_permissions=True,
                )

            # ── Step 2: Course Offerings for this cohort (fallback only) ──
            cohort_offerings = []
            if cohort and not child_courses:
                cohort_offerings = frappe.get_all(
                    "Course Offering",
                    filters={"cohort": cohort},
                    fields=[
                        "name", "course_name", "course_title",
                        "faculty", "credit_value", "status", "term_name",
                    ],
                    ignore_permissions=True,
                )

            # ── Step 3: build the display list ───────────────────────
            courses_out = []

            if child_courses:
                # course_offering is already on the child row — fetch faculty from it
                co_names = [ec.course_offering for ec in child_courses if ec.course_offering]
                co_details = {}
                if co_names:
                    for co in frappe.get_all(
                        "Course Offering",
                        filters={"name": ["in", co_names]},
                        fields=["name", "course_name", "faculty", "credit_value"],
                        ignore_permissions=True,
                    ):
                        co_details[co.name] = co

                for ec in child_courses:
                    co = co_details.get(ec.course_offering) or frappe._dict()
                    co_name = ec.course_offering or ""
                    att = att_map.get(co_name) or att_map.get(ec.course) or frappe._dict()

                    courses_out.append(_build_course_entry(
                        co_name=co_name,
                        course_id=ec.course or "",
                        course_name=co.get("course_name") or ec.course or "—",
                        faculty=co.get("faculty") or "—",
                        credits=co.get("credit_value") or ec.credits or 0,
                        course_type=ec.course_type or "—",
                        status=ec.status or "Enrolled",
                        att=att,
                    ))

            elif cohort_offerings:
                # Fallback: show all Course Offerings for the cohort
                for co in cohort_offerings:
                    co_name = co.name or ""
                    att = att_map.get(co_name) or att_map.get(co.course_title) or frappe._dict()

                    courses_out.append(_build_course_entry(
                        co_name=co_name,
                        course_id=co.course_title or "",
                        course_name=co.course_name or co.course_title or "—",
                        faculty=co.faculty or "—",
                        credits=co.credit_value or 0,
                        course_type="—",
                        status="Enrolled",
                        att=att,
                    ))

            # Sort: by course name
            courses_out.sort(key=lambda c: c["course_name"])

            # Cohort display name
            cohort_display = enr.term_name or cohort or "—"
            if cohort:
                cn = frappe.db.get_value("Batch", cohort, "cohort_name")
                if cn:
                    cohort_display = cn

            term_prefix = _get_term_prefix(enr.academic_year)
            term_label = _get_term_label(enr.term_name, term_prefix)

            enrollment_data.append({
                "enrollment": enr,
                "cohort_display": cohort_display,
                "term_label": term_label,
                "courses": courses_out,
                "course_count": len(courses_out),
                "total_credits": sum(c["credits"] for c in courses_out if c["credits"]),
            })

        context.enrollment_data = enrollment_data
        context.has_any_courses = any(ed["course_count"] > 0 for ed in enrollment_data)
        context.active_enrollment = enrollment_data[0] if enrollment_data else None

        # Build ordered term list for tabs
        import re as _re
        seen_terms = set()
        all_terms = []
        for ed in enrollment_data:
            if ed["course_count"] > 0 and ed["term_label"] not in seen_terms:
                all_terms.append(ed["term_label"])
                seen_terms.add(ed["term_label"])

        def _term_sort_key(t):
            nums = _re.findall(r'\d+', str(t))
            return int(nums[0]) if nums else 999

        all_terms.sort(key=_term_sort_key)

        # Active term = first Enrolled, else latest term
        active_term_label = None
        for ed in enrollment_data:
            if ed["enrollment"].get("status") == "Enrolled" and ed["course_count"] > 0:
                active_term_label = ed["term_label"]
                break
        if not active_term_label and all_terms:
            active_term_label = all_terms[-1]

        context.all_terms = all_terms
        context.active_term_label = active_term_label

    except Exception as e:
        frappe.log_error(f"Student Portal Courses error: {e}", "Student Portal")
        context.portal_error = str(e)
        _set_nav_defaults(context)

    return context


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_term_prefix(academic_year):
    """Return Semester/Trimester/Quarter/Year from Academic Year.academic_system."""
    if not academic_year:
        return "Term"
    try:
        sys = frappe.db.get_value("Academic Year", academic_year, "academic_system")
        if sys in ("Semester", "Trimester", "Quarter", "Year"):
            return sys
    except Exception:
        pass
    return "Term"


def _get_term_label(term_raw, prefix="Term"):
    """Resolve Cohort.term_name to a display label.

    Cohort.term_name is a free-text Data field — it may hold:
      - a plain number ("1", "2")  → formatted as "<prefix> <n>"  e.g. "Semester 1"
      - a full label ("Semester 1", "Trimester 2") → used as-is
    """
    if not term_raw:
        return "—"
    value = str(term_raw).strip()
    # Already a meaningful label (contains letters) — use directly
    if any(c.isalpha() for c in value):
        return value
    # Plain number — combine with prefix from Academic Year
    try:
        n = int(value)
        return f"{prefix} {n}"
    except (ValueError, TypeError):
        return value


def _build_course_entry(co_name, course_id, course_name, faculty, credits,
                        course_type, status, att):
    att_pct = round(float(att.get("attendance_percentage") or 0), 1) if att else 0.0
    return {
        "course_offering": co_name,
        "course": course_id,
        "course_name": course_name,
        "faculty": faculty or "—",
        "credits": credits or 0,
        "course_type": course_type or "—",
        "status": status or "Enrolled",
        "attendance_pct": att_pct,
        "eligible_for_exam": att.get("eligible_for_exam") if att else None,
        "total_class_hours": att.get("total_class_hours") or 0,
        "attended_classes": att.get("attended_classes") or 0,
        "total_classes": att.get("total_classes") or 0,
        "att_color": (
            "var(--sp-success)" if att_pct >= 75
            else "var(--sp-warning)" if att_pct >= 60
            else "var(--sp-danger)" if att_pct > 0
            else "var(--sp-text-4)"
        ),
    }


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
    context.student_name = full_name or student.name
    context.student_id = student.registration_id or student.name
    context.student_photo = student.passport_size_photo or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    context.programme_name = (
        frappe.db.get_value("Batch", student.programme, "cohort_name")
        or student.programme
        or ""
    )
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
