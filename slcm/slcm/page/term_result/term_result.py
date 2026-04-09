# Copyright (c) 2026, CU and contributors
# For license information, please see license.txt

import frappe
from collections import defaultdict


# ── Helpers ────────────────────────────────────────────────────────────────────

def _compute_term_gpa(exam_plan, student_names, students):
	"""Compute SGPA, term percentage and cumulative GPA for each student in-place."""
	if not student_names:
		return

	placeholders = ",".join(["%s"] * len(student_names))

	marks_rows = frappe.db.sql(
		f"""
		SELECT
			scm.student,
			scm.course,
			COALESCE(NULLIF(scm.updated_grade, ''), NULLIF(scm.grade, '')) AS final_grade,
			COALESCE(scm.updated_final_marks, scm.total_marks, 0)          AS final_marks,
			scm.consider_for_sgpa,
			scm.enrollment_status,
			COALESCE(c.credit_value, 0)                                     AS credit_value,
			COALESCE(gs.maximum_marks, 100)                                 AS maximum_marks,
			COALESCE(gsc.grade_point, 0)                                    AS grade_point,
			COALESCE(gsc.failed, 0)                                         AS is_failed
		FROM `tabStudent Course Marks` scm
		LEFT JOIN `tabCourse` c ON c.name = scm.course
		LEFT JOIN `tabCourse Schema Assignment` csa
			ON csa.exam_plan = %s AND csa.course = scm.course
		LEFT JOIN `tabGrading Schema` gs ON gs.name = csa.grade_schema
		LEFT JOIN `tabGrading Schema Component` gsc
			ON gsc.parent = csa.grade_schema
			AND gsc.grade = COALESCE(NULLIF(scm.updated_grade,''), NULLIF(scm.grade,''))
		WHERE scm.exam_plan = %s
		  AND scm.student IN ({placeholders})
		  AND COALESCE(scm.enrollment_status,'') NOT IN ('Dropped','Detained','Migrated')
		""",
		[exam_plan, exam_plan] + list(student_names),
		as_dict=True,
	)

	# Group marks by student
	student_marks = defaultdict(list)
	for m in marks_rows:
		student_marks[m.student].append(m)

	student_map = {s["student"]: s for s in students}

	for student_id, marks in student_marks.items():
		s = student_map.get(student_id)
		if not s:
			continue

		weighted_gp   = 0.0
		total_credits = 0.0
		total_marks   = 0.0
		total_max     = 0.0
		graded_count  = 0
		total_count   = len(marks)

		for m in marks:
			if m["consider_for_sgpa"] and m["final_grade"] and m["credit_value"]:
				weighted_gp   += float(m["grade_point"]) * float(m["credit_value"])
				total_credits += float(m["credit_value"])
			if m["final_grade"]:
				graded_count += 1
			total_marks += float(m["final_marks"] or 0)
			total_max   += float(m["maximum_marks"] or 100)

		all_graded = graded_count == total_count and total_count > 0

		s["term_gpa"]        = round(weighted_gp / total_credits, 2) if (total_credits > 0 and all_graded) else None
		s["term_percentage"] = round((total_marks / total_max) * 100, 2) if (total_max > 0 and all_graded) else None
		# CGPA comes directly from Student Master; cumulative % not available without historical data
		s["cumulative_gpa"]  = s.get("current_cgpa") or None
		s["cumulative_percentage"] = None


# ── Public API ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_term_stats(exam_plan):
	"""Return summary statistics for the exam plan."""
	if not exam_plan:
		return {}

	total = frappe.db.sql(
		"SELECT COUNT(DISTINCT student) AS cnt FROM `tabStudent Course Marks` WHERE exam_plan=%s",
		exam_plan, as_dict=True,
	)[0]["cnt"] or 0

	total_courses = frappe.db.sql(
		"SELECT COUNT(DISTINCT course) AS cnt FROM `tabStudent Course Marks` WHERE exam_plan=%s",
		exam_plan, as_dict=True,
	)[0]["cnt"] or 0

	# Graded = every course for that student has a non-empty grade
	graded_row = frappe.db.sql(
		"""
		SELECT COUNT(*) AS cnt FROM (
			SELECT student
			FROM `tabStudent Course Marks`
			WHERE exam_plan = %s
			GROUP BY student
			HAVING SUM(CASE WHEN COALESCE(NULLIF(grade,''),NULL) IS NULL THEN 1 ELSE 0 END) = 0
		) t
		""",
		exam_plan, as_dict=True,
	)
	graded = graded_row[0]["cnt"] if graded_row else 0

	# Average SGPA (only from students who have it calculated)
	avg_gpa = frappe.db.sql(
		"""
		SELECT AVG(current_cgpa) AS avg_gpa
		FROM `tabStudent Master` sm
		INNER JOIN `tabStudent Course Marks` scm ON scm.student = sm.name
		WHERE scm.exam_plan = %s AND sm.current_cgpa IS NOT NULL AND sm.current_cgpa > 0
		""",
		exam_plan, as_dict=True,
	)
	avg_gpa_val = avg_gpa[0]["avg_gpa"] if avg_gpa else None

	return {
		"total_students": total,
		"total_courses":  total_courses,
		"graded":         graded,
		"not_graded":     total - graded,
		"avg_cgpa":       round(float(avg_gpa_val), 2) if avg_gpa_val else None,
	}


@frappe.whitelist()
def get_exam_plans(search=None):
	"""Return exam plans for the plan selector."""
	filters = {}
	if search:
		filters["exam_name"] = ["like", f"%{search}%"]
	return frappe.get_all(
		"Exam Plan",
		filters=filters,
		fields=["name", "exam_name", "term", "status"],
		order_by="creation desc",
	)


@frappe.whitelist()
def get_term_students(exam_plan, search="", page=1, page_length=20,
                      sort_by="registration_id", sort_order="asc"):
	"""Return paginated students enrolled in the exam plan with term result data."""
	if not exam_plan:
		return {"students": [], "total": 0}

	page        = int(page)
	page_length = int(page_length)
	offset      = (page - 1) * page_length
	sort_dir    = "DESC" if sort_order == "desc" else "ASC"

	sort_col_map = {
		"registration_id": "sm.registration_id",
		"name":            "CONCAT_WS(' ', sm.first_name, sm.last_name)",
		"programme":       "sm.programme",
	}
	sort_col = sort_col_map.get(sort_by, "sm.registration_id")

	params       = {"exam_plan": exam_plan}
	search_cond  = ""
	if search:
		search_cond = (
			" AND (sm.registration_id LIKE %(search)s"
			" OR sm.first_name LIKE %(search)s"
			" OR sm.last_name LIKE %(search)s)"
		)
		params["search"] = f"%{search}%"

	students = frappe.db.sql(
		f"""
		SELECT
			sm.name                                                             AS student,
			sm.registration_id,
			TRIM(CONCAT_WS(' ', sm.first_name,
				COALESCE(NULLIF(sm.middle_name,''), NULL),
				sm.last_name))                                                  AS student_name,
			sm.student_status,
			sm.programme,
			sm.batch_year,
			sm.current_cgpa,
			sm.passport_size_photo                                                  AS image,
			sm.email,
			COUNT(DISTINCT scm.course)                                          AS course_count
		FROM `tabStudent Course Marks` scm
		INNER JOIN `tabStudent Master` sm ON sm.name = scm.student
		WHERE scm.exam_plan = %(exam_plan)s
		{search_cond}
		GROUP BY scm.student
		ORDER BY {sort_col} {sort_dir}
		LIMIT %(lim)s OFFSET %(off)s
		""",
		{**params, "lim": page_length, "off": offset},
		as_dict=True,
	)

	total_row = frappe.db.sql(
		f"""
		SELECT COUNT(DISTINCT scm.student) AS cnt
		FROM `tabStudent Course Marks` scm
		INNER JOIN `tabStudent Master` sm ON sm.name = scm.student
		WHERE scm.exam_plan = %(exam_plan)s
		{search_cond}
		""",
		params,
		as_dict=True,
	)
	total = total_row[0]["cnt"] if total_row else 0

	if students:
		_compute_term_gpa(exam_plan, [s["student"] for s in students], students)

	return {"students": students, "total": total}


@frappe.whitelist()
def get_student_courses(exam_plan, student):
	"""Return detailed course marks for a student in the exam plan (View popup)."""
	if not exam_plan or not student:
		return {"courses": [], "student": {}}

	# ── Student profile info ──────────────────────────────────────────────────
	sm = frappe.db.get_value(
		"Student Master",
		student,
		["first_name", "middle_name", "last_name", "registration_id",
		 "email", "programme", "batch_year", "passport_size_photo", "specialisation"],
		as_dict=True,
	) or {}

	# ── Course marks with grading schema data ─────────────────────────────────
	rows = frappe.db.sql(
		"""
		SELECT
			scm.course,
			c.course_name,
			c.course_code,
			COALESCE(c.credit_value, 0)                                      AS credit_value,
			c.course_type,
			scm.grade                                                         AS regular_grade,
			COALESCE(scm.total_marks, 0)                                      AS regular_marks,
			scm.moderated_grade,
			COALESCE(scm.updated_grade, '')                                   AS reexam_grade,
			COALESCE(scm.updated_final_marks, 0)                              AS reexam_marks,
			scm.consider_for_sgpa,
			scm.enrollment_status,
			scm.attendance_status,
			scm.status                                                        AS result_status,
			COALESCE(gs.maximum_marks, 100)                                   AS max_marks,
			COALESCE(gsc.failed, 0)                                           AS is_failed
		FROM `tabStudent Course Marks` scm
		LEFT JOIN `tabCourse` c ON c.name = scm.course
		LEFT JOIN `tabCourse Schema Assignment` csa
			ON csa.exam_plan = %(exam_plan)s AND csa.course = scm.course
		LEFT JOIN `tabGrading Schema` gs ON gs.name = csa.grade_schema
		LEFT JOIN `tabGrading Schema Component` gsc
			ON gsc.parent = csa.grade_schema
			AND gsc.grade = COALESCE(NULLIF(scm.updated_grade,''), NULLIF(scm.grade,''))
		WHERE scm.exam_plan = %(exam_plan)s
		  AND scm.student   = %(student)s
		ORDER BY c.course_code
		""",
		{"exam_plan": exam_plan, "student": student},
		as_dict=True,
	)

	# ── Per-course moderation marks sum ───────────────────────────────────────
	mod_rows = frappe.db.sql(
		"""
		SELECT scm.course, SUM(sme.moderated_marks) AS moderation_marks
		FROM `tabStudent Course Marks` scm
		INNER JOIN `tabStudent Marks Entry` sme ON sme.parent = scm.name
		WHERE scm.exam_plan = %(exam_plan)s
		  AND scm.student   = %(student)s
		  AND sme.moderated_marks IS NOT NULL
		  AND sme.moderated_marks != 0
		GROUP BY scm.course
		""",
		{"exam_plan": exam_plan, "student": student},
		as_dict=True,
	)
	mod_map = {r["course"]: r["moderation_marks"] for r in mod_rows}

	for row in rows:
		row["moderation_marks"] = mod_map.get(row["course"])

	return {"courses": rows, "student": sm}
