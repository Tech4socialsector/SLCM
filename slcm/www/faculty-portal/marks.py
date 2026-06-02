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
        faculty = frappe.get_doc("Faculty", faculty_name, ignore_permissions=True)
        set_faculty_nav(context, faculty)

        # ── Course offerings ────────────────────────────────────────
        course_offerings = frappe.get_all(
            "Course Offering",
            filters={"faculty": faculty_name, "status": "Active"},
            fields=["name", "course_name", "term_name", "academic_year"],
            order_by="course_name asc",
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

        if selected_co:
            raw_marks = frappe.get_all(
                "Student Course Marks",
                filters={"course_offering": selected_co if selected_co else ["in", co_names]},
                fields=["name", "student", "course", "course_offering",
                        "total_marks", "grade", "status", "remark",
                        "moderated_grade", "enrollment_status"],
                order_by="student asc",
                ignore_permissions=True,
            )

            for m in raw_marks:
                student_doc = frappe.db.get_value(
                    "Student Master", m.student,
                    ["first_name", "last_name", "registration_id"],
                    as_dict=True,
                ) or frappe._dict()
                full_name = " ".join(filter(None, [student_doc.first_name, student_doc.last_name]))
                marks_list.append({
                    "name": m.name,
                    "student": m.student,
                    "student_name": full_name or m.student,
                    "reg_id": student_doc.registration_id or m.student,
                    "total_marks": round(float(m.total_marks or 0), 2),
                    "grade": m.grade or "—",
                    "status": m.status or "Pending",
                    "remark": m.remark or "",
                    "moderated_grade": m.moderated_grade or "",
                })

            stats["total"] = len(marks_list)
            stats["graded"] = sum(1 for m in marks_list if m["grade"] and m["grade"] != "—")
            stats["passed"] = sum(1 for m in marks_list if m["status"] == "Pass")
            stats["failed"] = sum(1 for m in marks_list if m["status"] == "Fail")

        context.marks_list = marks_list
        context.marks_stats = stats

        # ── Evaluation Schemas for selected course ──────────────────
        context.eval_schemas = []
        if selected_co:
            try:
                exam_plan = frappe.db.get_value(
                    "Exam Plan",
                    {"course_offering": selected_co},
                    ["name", "evaluation_schema"],
                    as_dict=True,
                )
                if exam_plan and exam_plan.evaluation_schema:
                    schema = frappe.get_doc("Evaluation Schema", exam_plan.evaluation_schema, ignore_permissions=True)
                    context.eval_schemas = [{"name": schema.name, "components": []}]
            except Exception:
                pass

        context.selected_co_name = co_map.get(selected_co, frappe._dict()).get("course_name", selected_co) if selected_co else ""

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
