import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1

    # ── Guest redirect ─────────────────────────────────────────
    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "dashboard"

    # ── Find Student Master ────────────────────────────────────
    student_name = _get_student_name()
    if not student_name:
        context.no_student = True
        _set_nav_defaults(context)
        return context

    context.no_student = False

    try:
        student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
        _set_student_nav(context, student)

        # ── Active Enrollment ──────────────────────────────────
        enrollment = _get_active_enrollment(student_name)
        context.enrollment = enrollment

        # ── Stat: Course Count ─────────────────────────────────
        course_count = 0
        enrolled_courses = []
        if enrollment:
            enrolled_courses = frappe.get_all(
                "Student Enrollment Course",
                filters={"parent": enrollment.name},
                fields=["course_offering", "course", "credits", "status"],
                ignore_permissions=True
            )
            course_count = len(enrolled_courses)

        context.course_count = course_count

        # ── Stat: Attendance Summary ───────────────────────────
        att_summaries = frappe.get_all(
            "Attendance Summary",
            filters={"student": student_name},
            fields=["attendance_percentage", "eligible_for_exam", "course_offering", "course"],
            order_by="creation desc",
            limit=50,
            ignore_permissions=True
        )

        if att_summaries:
            pcts = [s.attendance_percentage or 0 for s in att_summaries]
            avg_att = round(sum(pcts) / len(pcts), 1)
        else:
            avg_att = 0.0

        context.avg_attendance = avg_att
        context.attendance_summaries = att_summaries[:5]

        # ── Stat: Outstanding Fees ─────────────────────────────
        fee_invoices = frappe.get_all(
            "Fee Invoice",
            filters={"student": student_name},
            fields=["name", "academic_term", "final_payable_amount", "paid_amount",
                    "outstanding_amount", "status", "due_date"],
            order_by="creation desc",
            limit=20,
            ignore_permissions=True
        )

        total_outstanding = sum(inv.outstanding_amount or 0 for inv in fee_invoices)
        context.total_outstanding = total_outstanding
        context.fee_invoices = fee_invoices[:3]
        context.has_dues = total_outstanding > 0

        # ── CGPA ──────────────────────────────────────────────
        context.cgpa = round(student.current_cgpa or 0.0, 2)

        # ── Recent courses for quick view ──────────────────────
        course_display = []
        for ec in enrolled_courses[:6]:
            co_name = ec.course_offering or ""
            co_data = {}
            if co_name:
                try:
                    co = frappe.db.get_value(
                        "Course Offering",
                        co_name,
                        ["course_name", "faculty", "credit_value", "term_name", "status"],
                        as_dict=True
                    )
                    if co:
                        co_data = co
                except Exception:
                    pass

            # Get attendance for this course
            att_pct = 0
            for s in att_summaries:
                if s.course_offering == co_name or s.course == ec.course:
                    att_pct = round(s.attendance_percentage or 0, 1)
                    break

            course_display.append({
                "course_offering": co_name,
                "course": ec.course or "",
                "course_name": co_data.get("course_name") or ec.course or "—",
                "credits": co_data.get("credit_value") or ec.credits or 0,
                "faculty": co_data.get("faculty") or "—",
                "term_name": co_data.get("term_name") or (enrollment.term_name if enrollment else ""),
                "status": ec.status or "Enrolled",
                "attendance_pct": att_pct,
            })

        context.courses_display = course_display

        # ── Upcoming / Today's Classes ─────────────────────────
        today = frappe.utils.today()
        try:
            upcoming_sessions = frappe.get_all(
                "Attendance Session",
                filters=[
                    ["session_date", ">=", today],
                    ["status", "=", "Active"]
                ],
                fields=["name", "session_date", "start_time", "course_offering",
                        "session_type", "venue"],
                order_by="session_date asc, start_time asc",
                limit=5,
                ignore_permissions=True
            )

            # Filter to only student's enrolled course offerings
            enrolled_co_set = {ec.course_offering for ec in enrolled_courses if ec.course_offering}
            context.upcoming_sessions = [
                s for s in upcoming_sessions if s.course_offering in enrolled_co_set
            ][:4]
        except Exception:
            context.upcoming_sessions = []

        # ── Student status info ────────────────────────────────
        context.student_status = student.student_status or "Active"
        context.registration_status = student.registration_status or ""
        context.current_term = student.current_term or ""
        context.current_year = student.current_year or ""
        context.academic_year = student.academic_year or ""
        context.is_hosteller = student.is_hosteller or 0

    except Exception as e:
        frappe.log_error(f"Student Portal Dashboard error: {e}", "Student Portal")
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


def _get_active_enrollment(student_name):
    enrollments = frappe.get_all(
        "Student Enrollment",
        filters={"student": student_name, "status": "Enrolled"},
        fields=["name", "cohort", "program", "academic_year", "term_name",
                "status", "faculty_advisor", "enrollment_date"],
        order_by="creation desc",
        limit=1,
        ignore_permissions=True
    )
    if enrollments:
        return enrollments[0]
    # Fallback: any enrollment
    all_enrollments = frappe.get_all(
        "Student Enrollment",
        filters={"student": student_name},
        fields=["name", "cohort", "program", "academic_year", "term_name",
                "status", "faculty_advisor", "enrollment_date"],
        order_by="creation desc",
        limit=1,
        ignore_permissions=True
    )
    return all_enrollments[0] if all_enrollments else None


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
