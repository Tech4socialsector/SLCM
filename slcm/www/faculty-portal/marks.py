import frappe
from slcm.utils.faculty_portal import get_faculty_name, set_faculty_nav, set_nav_defaults, set_portal_settings

no_cache = 1


def get_context(context):
    context.no_cache = 1
    set_portal_settings(context)

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "marks"

    faculty_name = get_faculty_name()
    if not faculty_name:
        context.not_a_faculty = True
        set_nav_defaults(context)
        _set_defaults(context)
        return context

    context.not_a_faculty = False

    try:
        faculty = frappe.get_doc("Faculty", faculty_name)
        set_faculty_nav(context, faculty)

        # ── Course offerings for this faculty ────────────────────────
        # course_title is the Link → Course; course_name is a Data display field
        # Course Offering status options are only "Open" and "Closed"
        course_offerings = frappe.get_all(
            "Course Offering",
            filters={"faculty": faculty_name, "status": "Open"},
            fields=["name", "course_name", "course_title", "term_name", "academic_year"],
            order_by="academic_year desc, term_name asc, course_name asc",
            ignore_permissions=True,
        )
        context.course_offerings = course_offerings
        co_names = [c.name for c in course_offerings]
        co_map = {c.name: c for c in course_offerings}

        # ── Filter from URL params ──────────────────────────────────
        selected_co = frappe.request.args.get("course_offering", "") if frappe.request else ""
        if selected_co not in co_names:
            selected_co = co_names[0] if co_names else ""
        context.selected_co = selected_co

        # ── Student marks for selected course offering ──────────────
        marks_list = []
        stats = {"total": 0, "graded": 0, "passed": 0, "failed": 0}
        exam_plan = None
        context.result_locked = False
        context.result_view_blocked = False
        context.view_deadline_expired = False
        context.edit_deadline_expired = False
        context.mask_student_info = 0

        if selected_co:
            co_doc = co_map[selected_co]
            # course_title is the Link field pointing to Course doctype
            course_link = co_doc.get("course_title") or ""

            if course_link:
                # Resolve the active exam plan for this course via Course Schema Assignment
                assignment = frappe.db.sql(
                    """
                    SELECT csa.exam_plan, csa.evaluation_schema, csa.grade_schema
                    FROM `tabCourse Schema Assignment` csa
                    JOIN `tabExam Plan` ep ON ep.name = csa.exam_plan
                    WHERE csa.course = %(course)s
                    ORDER BY FIELD(ep.status, 'Active', 'Inactive') ASC, ep.creation DESC
                    LIMIT 1
                    """,
                    {"course": course_link},
                    as_dict=True,
                )

                if assignment:
                    exam_plan = assignment[0]["exam_plan"]
                    grade_schema = assignment[0].get("grade_schema") or ""

                    # Read Access Result Settings for this exam_plan + course
                    access = frappe.db.get_value(
                        "Access Result Settings",
                        {"exam_plan": exam_plan, "course": course_link},
                        ["view_access", "view_deadline", "edit_access", "edit_deadline",
                         "status", "mask_student_info"],
                        as_dict=True,
                    ) or frappe._dict({
                        "view_access": 1, "view_deadline": None,
                        "edit_access": 1, "edit_deadline": None,
                        "status": "UNLOCKED", "mask_student_info": 0,
                    })

                    now = frappe.utils.now_datetime()

                    # view_access is blocked if the flag is off OR its deadline has passed
                    view_deadline = access.get("view_deadline")
                    view_expired = bool(view_deadline and now > frappe.utils.get_datetime(view_deadline))
                    context.result_view_blocked = (
                        not int(access.get("view_access") or 1) or view_expired
                    )
                    context.view_deadline_expired = view_expired

                    # edit is locked if status=LOCKED, edit_access flag is off, or edit deadline passed
                    edit_deadline = access.get("edit_deadline")
                    edit_expired = bool(edit_deadline and now > frappe.utils.get_datetime(edit_deadline))
                    context.result_locked = (
                        access.get("status") == "LOCKED"
                        or not int(access.get("edit_access") or 1)
                        or edit_expired
                    )
                    context.edit_deadline_expired = edit_expired

                    context.mask_student_info = int(access.get("mask_student_info") or 0)

                    # If view access is disabled, skip loading marks entirely
                    if context.result_view_blocked:
                        context.marks_list = []
                        context.marks_stats = {"total": 0, "graded": 0, "passed": 0, "failed": 0}
                        return context

                    # Determine which grades are failing grades
                    failed_grades = set()
                    if grade_schema:
                        try:
                            gs = frappe.get_doc("Grading Schema", grade_schema)
                            failed_grades = {r.grade for r in gs.grades if r.failed}
                        except Exception:
                            pass

                    raw_marks = frappe.get_all(
                        "Student Course Marks",
                        filters={"course": course_link, "exam_plan": exam_plan},
                        fields=["name", "student", "course", "exam_plan",
                                "total_marks", "grade", "status", "remark",
                                "moderated_grade", "enrollment_status"],
                        order_by="student asc",
                        ignore_permissions=True,
                    )

                    for idx, m in enumerate(raw_marks):
                        student_doc = frappe.db.get_value(
                            "Student Master", m.student,
                            ["first_name", "last_name", "registration_id"],
                            as_dict=True,
                        ) or frappe._dict()
                        if context.mask_student_info:
                            # Replace identifying info with anonymised labels
                            full_name = f"Student {idx + 1}"
                            reg_id = "—"
                        else:
                            full_name = " ".join(filter(None, [student_doc.first_name, student_doc.last_name]))
                            reg_id = student_doc.registration_id or m.student
                        grade = (m.grade or "").strip()
                        if grade:
                            result_status = "Fail" if grade in failed_grades else "Pass"
                        else:
                            result_status = "Pending"
                        marks_list.append({
                            "name": m.name,
                            "student": m.student,
                            "student_name": full_name or m.student,
                            "reg_id": reg_id,
                            "total_marks": round(float(m.total_marks or 0), 2),
                            "grade": grade or "—",
                            "status": result_status,
                            "remark": m.remark or "",
                            "moderated_grade": m.moderated_grade or "",
                        })

            stats["total"] = len(marks_list)
            stats["graded"] = sum(1 for m in marks_list if m["grade"] and m["grade"] != "—")
            stats["passed"] = sum(1 for m in marks_list if m["status"] == "Pass")
            stats["failed"] = sum(1 for m in marks_list if m["status"] == "Fail")

        context.marks_list = marks_list
        context.marks_stats = stats

        # ── Evaluation schema for selected course ───────────────────
        context.eval_schemas = []
        if selected_co and exam_plan:
            try:
                co_doc = co_map[selected_co]
                course_link = co_doc.get("course_title") or ""
                if course_link:
                    ep_row = frappe.db.get_value(
                        "Course Schema Assignment",
                        {"course": course_link, "exam_plan": exam_plan},
                        "evaluation_schema",
                    )
                    if ep_row:
                        schema = frappe.get_doc("Evaluation Schema", ep_row)
                        context.eval_schemas = [{"name": schema.name, "components": []}]
            except Exception:
                pass

        context.selected_co_name = (
            co_map.get(selected_co, frappe._dict()).get("course_name", selected_co)
            if selected_co else ""
        )

    except Exception as e:
        frappe.log_error(f"Faculty Portal Marks error: {e}", "Faculty Portal")
        context.portal_error = str(e)
        set_nav_defaults(context)
        _set_defaults(context)

    return context


def _set_defaults(context):
    context.course_offerings = []
    context.selected_co = ""
    context.selected_co_name = ""
    context.marks_list = []
    context.marks_stats = {"total": 0, "graded": 0, "passed": 0, "failed": 0}
    context.eval_schemas = []
    context.result_locked = False
    context.result_view_blocked = False
    context.view_deadline_expired = False
    context.edit_deadline_expired = False
    context.mask_student_info = 0
