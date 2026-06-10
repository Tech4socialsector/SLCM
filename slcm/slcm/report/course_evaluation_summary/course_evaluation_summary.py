import frappe


def execute(filters=None):
    filters = filters or {}
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data


def get_columns(filters):
    return [
        {"label": "Exam Plan", "fieldname": "exam_plan", "fieldtype": "Link", "options": "Exam Plan", "width": 160},
        {"label": "Course", "fieldname": "course", "fieldtype": "Link", "options": "Course", "width": 160},
        {"label": "Component", "fieldname": "component", "fieldtype": "Data", "width": 150},
        {"label": "Assessment Type", "fieldname": "assessment_type", "fieldtype": "Data", "width": 150},
        {"label": "Students Assessed", "fieldname": "student_count", "fieldtype": "Int", "width": 130},
        {"label": "Max Marks", "fieldname": "max_marks", "fieldtype": "Float", "width": 100},
        {"label": "Avg Marks", "fieldname": "avg_marks", "fieldtype": "Float", "width": 100},
        {"label": "Min Marks", "fieldname": "min_marks", "fieldtype": "Float", "width": 100},
        {"label": "Pass Count", "fieldname": "pass_count", "fieldtype": "Int", "width": 100},
        {"label": "Fail Count", "fieldname": "fail_count", "fieldtype": "Int", "width": 100},
        {"label": "Pass %", "fieldname": "pass_pct", "fieldtype": "Percent", "width": 100},
    ]


def get_data(filters):
    conditions = "scm.docstatus <= 1"

    if filters.get("exam_plan"):
        conditions += " AND scm.exam_plan = %(exam_plan)s"
    if filters.get("course"):
        conditions += " AND scm.course = %(course)s"
    if filters.get("student"):
        conditions += " AND scm.student = %(student)s"
    if filters.get("academic_year"):
        conditions += " AND ep.term = %(academic_year)s"

    rows = frappe.db.sql(f"""
        SELECT
            scm.exam_plan,
            scm.course,
            sme.component,
            sme.assessment_type,
            COUNT(DISTINCT scm.student)                          AS student_count,
            MAX(COALESCE(sme.moderated_marks, sme.marks))        AS max_marks,
            AVG(COALESCE(sme.moderated_marks, sme.marks))        AS avg_marks,
            MIN(COALESCE(sme.moderated_marks, sme.marks))        AS min_marks,
            SUM(CASE WHEN COALESCE(sme.moderated_marks, sme.marks) >= 0 THEN 1 ELSE 0 END) AS pass_count,
            0 AS fail_count
        FROM `tabStudent Course Marks` scm
        JOIN `tabStudent Marks Entry` sme ON sme.parent = scm.name
        LEFT JOIN `tabExam Plan` ep ON ep.name = scm.exam_plan
        WHERE {conditions}
        GROUP BY scm.exam_plan, scm.course, sme.component, sme.assessment_type
        ORDER BY scm.exam_plan, scm.course, sme.component
    """, filters, as_dict=True)

    for row in rows:
        total = row.get("student_count") or 0
        passed = row.get("pass_count") or 0
        row["fail_count"] = total - passed
        row["pass_pct"] = round((passed / total * 100), 2) if total else 0.0
        if row.get("avg_marks") is not None:
            row["avg_marks"] = round(row["avg_marks"], 2)

    return rows
