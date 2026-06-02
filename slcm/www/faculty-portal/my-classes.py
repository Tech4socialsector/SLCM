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
    context.active_page = "my_classes"

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

        # ── Fetch all course offerings for this faculty ────────────
        course_offerings = frappe.get_all(
            "Course Offering",
            filters={"faculty": faculty_name},
            fields=["name", "course_name", "course_title", "term_name",
                    "academic_year", "credit_value", "maximum_students", "status"],
            order_by="academic_year desc, term_name desc, course_name asc",
            ignore_permissions=True,
        )

        # ── Enrich each offering ───────────────────────────────────
        enriched = []
        for co in course_offerings:
            # Student group count & student count
            groups = frappe.get_all(
                "Student Group",
                filters={"course_offering": co.name},
                fields=["name"],
                ignore_permissions=True,
            )
            group_names = [g.name for g in groups]

            student_count = 0
            if group_names:
                try:
                    res = frappe.db.sql(
                        """SELECT COUNT(DISTINCT student) AS cnt
                           FROM `tabStudent Group Student`
                           WHERE parent IN %s AND active = 1""",
                        (tuple(group_names),),
                        as_dict=True,
                    )
                    student_count = (res[0].cnt or 0) if res else 0
                except Exception:
                    student_count = 0

            # Average attendance for this course offering
            att_summaries = frappe.get_all(
                "Attendance Summary",
                filters={"course_offering": co.name},
                fields=["attendance_percentage"],
                ignore_permissions=True,
            )
            avg_att = 0.0
            if att_summaries:
                pcts = [float(s.attendance_percentage or 0) for s in att_summaries]
                avg_att = round(sum(pcts) / len(pcts), 1)

            # Total sessions conducted
            total_sessions = frappe.db.count(
                "Attendance Session",
                filters={"course_offering": co.name},
            )

            enriched.append({
                "name": co.name,
                "course_name": co.course_name or co.name,
                "term_name": co.term_name or "—",
                "academic_year": co.academic_year or "—",
                "credits": co.credit_value or 0,
                "student_count": student_count,
                "avg_attendance": avg_att,
                "total_sessions": total_sessions,
                "status": co.status or "Active",
                "group_count": len(group_names),
            })

        context.course_offerings = enriched

        # ── Filter options ─────────────────────────────────────────
        terms = sorted(set(c["term_name"] for c in enriched if c["term_name"] != "—"))
        years = sorted(set(c["academic_year"] for c in enriched if c["academic_year"] != "—"), reverse=True)
        context.filter_terms = terms
        context.filter_years = years

    except Exception as e:
        frappe.log_error(f"Faculty Portal My Classes error: {e}", "Faculty Portal")
        context.portal_error = str(e)
        set_nav_defaults(context)
        _set_defaults(context)

    return context


def _set_defaults(context):
    context.course_offerings = []
    context.filter_terms = []
    context.filter_years = []
