import frappe


def execute(filters=None):
    filters = filters or {}

    if not filters.get("student"):
        frappe.throw("Please select a Student to generate the marksheet.")

    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Exam Plan", "fieldname": "exam_plan", "fieldtype": "Link", "options": "Exam Plan", "width": 160},
        {"label": "Course", "fieldname": "course", "fieldtype": "Link", "options": "Course", "width": 160},
        {"label": "Component", "fieldname": "component", "fieldtype": "Data", "width": 150},
        {"label": "Assessment Type", "fieldname": "assessment_type", "fieldtype": "Data", "width": 150},
        {"label": "Label", "fieldname": "label", "fieldtype": "Data", "width": 120},
        {"label": "Marks", "fieldname": "marks", "fieldtype": "Float", "width": 80},
        {"label": "Revaluation Marks", "fieldname": "revaluation_marks", "fieldtype": "Float", "width": 130},
        {"label": "Moderated Marks", "fieldname": "moderated_marks", "fieldtype": "Float", "width": 120},
        {"label": "Final Marks", "fieldname": "final_marks", "fieldtype": "Float", "width": 100},
        {"label": "Course Total", "fieldname": "course_total", "fieldtype": "Float", "width": 110},
        {"label": "Grade", "fieldname": "grade", "fieldtype": "Data", "width": 80},
        {"label": "Moderated Grade", "fieldname": "moderated_grade", "fieldtype": "Data", "width": 120},
        {"label": "Term GPA", "fieldname": "term_gpa", "fieldtype": "Float", "width": 100},
        {"label": "Term %", "fieldname": "term_percentage", "fieldtype": "Percent", "width": 100},
        {"label": "Cumulative GPA", "fieldname": "cumulative_gpa", "fieldtype": "Float", "width": 120},
        {"label": "Cumulative %", "fieldname": "cumulative_percentage", "fieldtype": "Percent", "width": 120},
    ]


def get_data(filters):
    conditions = "scm.student = %(student)s"

    if filters.get("exam_plan"):
        conditions += " AND scm.exam_plan = %(exam_plan)s"

    rows = frappe.db.sql(f"""
        SELECT
            scm.exam_plan,
            scm.course,
            sme.component,
            sme.assessment_type,
            sme.label,
            sme.marks,
            sme.revaluation_marks,
            sme.moderated_marks,
            COALESCE(sme.moderated_marks, sme.revaluation_marks, sme.marks) AS final_marks,
            scm.total_marks AS course_total,
            scm.grade,
            scm.moderated_grade,
            srp.term_gpa,
            srp.term_percentage,
            srp.cumulative_gpa,
            srp.cumulative_percentage
        FROM `tabStudent Course Marks` scm
        JOIN `tabStudent Marks Entry` sme ON sme.parent = scm.name
        LEFT JOIN `tabStudent Result Publish` srp
            ON srp.student = scm.student AND srp.exam_plan = scm.exam_plan
        WHERE {conditions}
        ORDER BY scm.exam_plan, scm.course, sme.component
    """, filters, as_dict=True)

    # suppress repeated GPA values (show only on first row per exam_plan)
    seen_plan = {}
    for row in rows:
        key = row.get("exam_plan")
        if key in seen_plan:
            row["term_gpa"] = None
            row["term_percentage"] = None
            row["cumulative_gpa"] = None
            row["cumulative_percentage"] = None
        else:
            seen_plan[key] = True

    return rows
