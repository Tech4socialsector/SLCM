# Copyright (c) 2026, CU and contributors
# For license information, please see license.txt

import frappe


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_or_create_access(exam_plan, course):
	"""Return the Course Result Access doc for the given exam_plan+course, creating if absent."""
	existing = frappe.db.get_value(
		"Course Result Access",
		{"exam_plan": exam_plan, "course": course},
		"name",
	)
	if existing:
		return frappe.get_doc("Course Result Access", existing)
	doc = frappe.new_doc("Course Result Access")
	doc.exam_plan    = exam_plan
	doc.course       = course
	doc.status       = "UNLOCKED"
	doc.view_access  = 1
	doc.edit_access  = 1
	doc.insert(ignore_permissions=True)
	return doc


def _access_map(exam_plan):
	"""Return a dict of course → Course Result Access row (without child tables)."""
	rows = frappe.db.sql(
		"""
		SELECT
			cra.name, cra.course,
			cra.view_access, cra.view_deadline, cra.edit_access, cra.edit_deadline,
			cra.auto_generate_grade_access, cra.edit_grade_access,
			cra.relative_grading_access, cra.mask_student_info,
			cra.generate_grade_report, cra.moderation_policy_access,
			cra.status
		FROM `tabCourse Result Access` cra
		WHERE cra.exam_plan = %(exam_plan)s
		""",
		{"exam_plan": exam_plan},
		as_dict=True,
	)
	return {r["course"]: r for r in rows}


def _evaluator_map(exam_plan):
	"""Return a dict of course → list of evaluator dicts for the given exam plan.

	evaluator_name is a Link to Faculty; we fetch the faculty's full name and
	email from the Faculty doctype for display.
	"""
	rows = frappe.db.sql(
		"""
		SELECT
			cra.course,
			rce.evaluator_type,
			rce.evaluator_name,
			rce.evaluator_email,
			f.faculty_name
		FROM `tabResult Course Evaluator` rce
		INNER JOIN `tabCourse Result Access` cra ON rce.parent = cra.name
		LEFT JOIN `tabFaculty` f ON f.name = rce.evaluator_name
		WHERE cra.exam_plan = %(exam_plan)s
		""",
		{"exam_plan": exam_plan},
		as_dict=True,
	)
	result = {}
	for r in rows:
		result.setdefault(r["course"], []).append({
			"evaluator_type":  r["evaluator_type"],
			"evaluator_name":  r["evaluator_name"],
			"evaluator_display": r.get("faculty_name") or r["evaluator_name"] or "",
			"evaluator_email": r["evaluator_email"],
		})
	return result


def _visibility_map(exam_plan):
	"""Return a dict of course → list of exam type dicts for the given exam plan.

	exam_type is a Link to Exam Assessment Type; we fetch type_name for display.
	"""
	rows = frappe.db.sql(
		"""
		SELECT cra.course, rev.exam_type, eat.type_name
		FROM `tabResult Exam Visibility` rev
		INNER JOIN `tabCourse Result Access` cra ON rev.parent = cra.name
		LEFT JOIN `tabExam Assessment Type` eat ON eat.name = rev.exam_type
		WHERE cra.exam_plan = %(exam_plan)s
		""",
		{"exam_plan": exam_plan},
		as_dict=True,
	)
	result = {}
	for r in rows:
		result.setdefault(r["course"], []).append({
			"name":      r["exam_type"],
			"type_name": r.get("type_name") or r["exam_type"] or "",
		})
	return result


# ── Public API ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_exam_plans(search=None):
	"""Return all exam plans for the term selector."""
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
def get_courses_for_result(exam_plan, search=""):
	"""
	Return all courses with their result-access settings for the given exam plan.
	Mirrors the Access Results table in the UI.
	"""
	if not exam_plan:
		frappe.throw("Exam Plan is required.")

	page_length = 500

	if search:
		courses = frappe.db.sql(
			"""
			SELECT name, course_name, course_code, department_name
			FROM `tabCourse`
			WHERE course_name LIKE %(s)s OR course_code LIKE %(s)s
			ORDER BY course_name ASC
			LIMIT %(limit)s
			""",
			{"s": f"%{search}%", "limit": page_length},
			as_dict=True,
		)
	else:
		courses = frappe.get_all(
			"Course",
			fields=["name", "course_name", "course_code", "department_name"],
			order_by="course_name asc",
			page_length=page_length,
		)

	amap = _access_map(exam_plan)
	emap = _evaluator_map(exam_plan)
	vmap = _visibility_map(exam_plan)

	for c in courses:
		acc = amap.get(c["name"], {})
		c["evaluators"]                 = emap.get(c["name"], [])
		c["view_access"]                = int(acc.get("view_access", 1))
		c["view_deadline"]              = str(acc.get("view_deadline") or "")
		c["edit_access"]                = int(acc.get("edit_access", 1))
		c["edit_deadline"]              = str(acc.get("edit_deadline") or "")
		c["auto_generate_grade_access"] = int(acc.get("auto_generate_grade_access", 0))
		c["edit_grade_access"]          = int(acc.get("edit_grade_access", 0))
		c["relative_grading_access"]    = int(acc.get("relative_grading_access", 0))
		c["mask_student_info"]          = int(acc.get("mask_student_info", 0))
		c["generate_grade_report"]      = int(acc.get("generate_grade_report", 0))
		c["moderation_policy_access"]   = int(acc.get("moderation_policy_access", 0))
		c["status"]                     = acc.get("status", "UNLOCKED")
		# list of {name, type_name} dicts — name is the Exam Assessment Type link
		c["visible_exams"]              = vmap.get(c["name"], [])

	return courses


@frappe.whitelist()
def save_access_settings(exam_plan, courses, settings):
	"""
	Bulk-update access settings for the selected courses.

	courses  – JSON list of course names
	settings – JSON dict with fields:
	           view_access, view_deadline, edit_access, edit_deadline,
	           auto_generate_grade_access, edit_grade_access,
	           relative_grading_access, mask_student_info,
	           generate_grade_report, moderation_policy_access
	"""
	import json

	if isinstance(courses, str):
		courses = json.loads(courses)
	if isinstance(settings, str):
		settings = json.loads(settings)

	if not courses:
		frappe.throw("No courses selected.")

	_ALLOWED = {
		"view_access", "view_deadline", "edit_access", "edit_deadline",
		"auto_generate_grade_access", "edit_grade_access",
		"relative_grading_access", "mask_student_info",
		"generate_grade_report", "moderation_policy_access",
	}

	for course in courses:
		doc = _get_or_create_access(exam_plan, course)
		for key, val in settings.items():
			if key in _ALLOWED:
				setattr(doc, key, val)
		doc.save(ignore_permissions=True)

	frappe.db.commit()
	return True


@frappe.whitelist()
def assign_evaluator(exam_plan, courses, evaluators):
	"""
	Add one or more evaluators to the selected courses (append, do not replace).

	courses    – JSON list of course names
	evaluators – JSON list of dicts:
	             [{ evaluator_type, evaluator_name (Faculty name/link), evaluator_email }, ...]
	             evaluator_email is auto-fetched from the Faculty record when evaluator_type
	             is 'Custom'; pass it explicitly when available.
	"""
	import json

	if isinstance(courses, str):
		courses = json.loads(courses)
	if isinstance(evaluators, str):
		evaluators = json.loads(evaluators)

	if not courses:
		frappe.throw("No courses selected.")
	if not evaluators:
		frappe.throw("No evaluators provided.")

	for course in courses:
		doc = _get_or_create_access(exam_plan, course)

		# Existing Faculty name set (Link field) to avoid duplicates
		existing_names = {
			(row.evaluator_name or "").strip()
			for row in doc.evaluators
		}

		for ev in evaluators:
			ev_type  = ev.get("evaluator_type", "Class Faculty")
			fac_name = (ev.get("evaluator_name") or "").strip()

			# Deduplicate by Faculty name for Custom; one Class Faculty entry per course
			if ev_type == "Class Faculty":
				if any(r.evaluator_type == "Class Faculty" for r in doc.evaluators):
					continue
			else:
				if fac_name and fac_name in existing_names:
					continue

			# Resolve email from Faculty record if not provided
			email = (ev.get("evaluator_email") or "").strip()
			if not email and fac_name:
				email = frappe.db.get_value("Faculty", fac_name, "email") or ""

			doc.append("evaluators", {
				"evaluator_type":  ev_type,
				"evaluator_name":  fac_name,   # Link → Faculty
				"evaluator_email": email,
			})
			if fac_name:
				existing_names.add(fac_name)

		doc.save(ignore_permissions=True)

	frappe.db.commit()
	return True


@frappe.whitelist()
def remove_evaluator(exam_plan, course, evaluator_name):
	"""
	Remove a specific evaluator by Faculty name (Link value) from a course.
	For Class Faculty rows with no name, pass evaluator_name='' and
	evaluator_type='Class Faculty' — removes the first Class Faculty row.
	"""
	name = frappe.db.get_value(
		"Course Result Access",
		{"exam_plan": exam_plan, "course": course},
		"name",
	)
	if not name:
		return True

	doc = frappe.get_doc("Course Result Access", name)
	target = (evaluator_name or "").strip()

	if target:
		# Remove by Faculty link name
		doc.set(
			"evaluators",
			[row for row in doc.evaluators if (row.evaluator_name or "").strip() != target],
		)
	else:
		# Remove the first Class Faculty entry (no link)
		removed = False
		kept = []
		for row in doc.evaluators:
			if not removed and row.evaluator_type == "Class Faculty" and not row.evaluator_name:
				removed = True
				continue
			kept.append(row)
		doc.set("evaluators", kept)

	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return True


@frappe.whitelist()
def save_exam_visibility(exam_plan, courses, exam_types):
	"""
	Set the visible exam types for the selected courses (replaces existing).

	exam_types – JSON list of Exam Assessment Type names (the Link field value),
	             e.g. ["End Term Exam", "Mid-Term Exam"]
	"""
	import json

	if isinstance(courses, str):
		courses = json.loads(courses)
	if isinstance(exam_types, str):
		exam_types = json.loads(exam_types)

	if not courses:
		frappe.throw("No courses selected.")

	# Validate each exam_type exists in Exam Assessment Type
	valid_types = set(
		frappe.get_all("Exam Assessment Type", pluck="name")
	)

	for course in courses:
		doc = _get_or_create_access(exam_plan, course)
		doc.set("visible_exams", [])
		for et in exam_types:
			if et and et in valid_types:
				doc.append("visible_exams", {"exam_type": et})
		doc.save(ignore_permissions=True)

	frappe.db.commit()
	return True


@frappe.whitelist()
def get_faculty_list(search=""):
	"""
	Return Faculty records for the Assign Evaluator custom search box.
	evaluator_name is a Link to Faculty, so we search the Faculty doctype.
	"""
	filters = {}
	if search:
		filters["faculty_name"] = ["like", f"%{search}%"]

	return frappe.get_all(
		"Faculty",
		filters=filters,
		fields=["name", "faculty_name", "email", "image"],
		order_by="faculty_name asc",
		page_length=20,
	)


@frappe.whitelist()
def get_exam_types(search=""):
	"""
	Return Exam Assessment Type records for the Exam Visibility modal.
	exam_type is a Link to Exam Assessment Type, so we always load from that doctype.
	Returns: [{ name, type_name, assessment_type }, ...]
	         where `name` is the Link value to store in visible_exams.exam_type.
	"""
	filters = {"is_active": 1}
	if search:
		filters["type_name"] = ["like", f"%{search}%"]

	records = frappe.get_all(
		"Exam Assessment Type",
		filters=filters,
		fields=["name", "type_name", "assessment_type"],
		order_by="type_name asc",
	)
	return records


@frappe.whitelist()
def get_departments(search=""):
	"""Return departments for the Course Results page department filter."""
	filters = {"status": "Active"}
	if search:
		filters["department_name"] = ["like", f"%{search}%"]
	return frappe.get_all(
		"Department",
		filters=filters,
		fields=["name", "department_name"],
		order_by="department_name asc",
		page_length=100,
	)


@frappe.whitelist()
def get_courses_by_department(department, exam_plan=None, search=""):
	"""Return courses in a department that have class configurations."""
	course_filters = {"department": department}
	if search:
		course_filters["course_name"] = ["like", f"%{search}%"]
	return frappe.get_all(
		"Course",
		filters=course_filters,
		fields=["name", "course_name", "course_code", "credit_value"],
		order_by="course_name asc",
		page_length=200,
	)


# ── New Course Results Page API ────────────────────────────────────────────────

def _get_marks_columns(evaluation_schema):
	"""Return ordered assessment config columns for a given evaluation schema."""
	rows = frappe.db.sql(
		"""
		SELECT sac.name, sac.component, ec.component_name,
		       sac.assessment_type, eat.type_name,
		       sac.label, sac.maximum_marks, sac.effective_marks,
		       sac.consider_for_pass_fail, sac.enrollment, sac.idx
		FROM `tabSchema Assessment Config` sac
		LEFT JOIN `tabExam Component` ec ON ec.name = sac.component
		LEFT JOIN `tabExam Assessment Type` eat ON eat.name = sac.assessment_type
		WHERE sac.parent = %(schema)s
		ORDER BY sac.idx ASC
		""",
		{"schema": evaluation_schema},
		as_dict=True,
	)
	# Ensure type_name falls back to assessment_type when JOIN returns NULL
	for row in rows:
		if not row.get("type_name"):
			row["type_name"] = row.get("assessment_type") or ""
		if not row.get("component_name"):
			row["component_name"] = row.get("component") or ""
	return rows


def _get_reexam_columns(evaluation_schema):
	"""Return ordered reexam config columns for a given evaluation schema."""
	rows = frappe.db.sql(
		"""
		SELECT src.name, src.component, ec.component_name,
		       src.assessment_type, eat.type_name,
		       src.label, src.maximum_marks, src.effective_marks,
		       src.enrollment, src.re_exam_type_category, src.idx
		FROM `tabSchema Reexam Config` src
		LEFT JOIN `tabExam Component` ec ON ec.name = src.component
		LEFT JOIN `tabExam Assessment Type` eat ON eat.name = src.assessment_type
		WHERE src.parent = %(schema)s
		ORDER BY src.idx ASC
		""",
		{"schema": evaluation_schema},
		as_dict=True,
	)
	for row in rows:
		if not row.get("type_name"):
			row["type_name"] = row.get("assessment_type") or ""
		if not row.get("component_name"):
			row["component_name"] = row.get("component") or ""
	return rows


@frappe.whitelist()
def get_course_info(course):
	"""Return full course info for the Course Results page."""
	course_doc = frappe.db.get_value(
		"Course", course,
		["course_name", "course_code", "credit_value", "department_name", "department"],
		as_dict=True,
	) or {}

	# Find best exam plan (Active first, then most recent)
	assignment = frappe.db.sql(
		"""
		SELECT csa.exam_plan, csa.evaluation_schema, csa.grade_schema,
		       ep.exam_name, ep.status AS plan_status
		FROM `tabCourse Schema Assignment` csa
		JOIN `tabExam Plan` ep ON ep.name = csa.exam_plan
		WHERE csa.course = %(course)s
		ORDER BY FIELD(ep.status, 'Active', 'Inactive') ASC, ep.creation DESC
		LIMIT 1
		""",
		{"course": course},
		as_dict=True,
	)
	assignment = assignment[0] if assignment else {}

	access = frappe.db.get_value(
		"Course Result Access",
		{"exam_plan": assignment.get("exam_plan"), "course": course},
		["view_access", "edit_access", "edit_deadline", "mask_student_info",
		 "auto_generate_grade_access", "status"],
		as_dict=True,
	) or {}

	count_row = frappe.db.sql(
		"""
		SELECT COUNT(DISTINCT scm.student) AS cnt
		FROM `tabStudent Course Marks` scm
		WHERE scm.course = %(course)s
		  AND scm.exam_plan = %(exam_plan)s
		""",
		{"course": course, "exam_plan": assignment.get("exam_plan", "")},
		as_dict=True,
	)

	columns = []
	reexam_columns = []
	if assignment.get("evaluation_schema"):
		columns = _get_marks_columns(assignment["evaluation_schema"])
		reexam_columns = _get_reexam_columns(assignment["evaluation_schema"])

	# Format edit_deadline for display
	edit_deadline = ""
	raw_dl = access.get("edit_deadline")
	if raw_dl:
		try:
			edit_deadline = frappe.utils.format_datetime(str(raw_dl), "dd MMM yy hh:mm a")
		except Exception:
			edit_deadline = str(raw_dl)

	return {
		"course_name":     course_doc.get("course_name", ""),
		"course_code":     course_doc.get("course_code", ""),
		"credit_value":    course_doc.get("credit_value", 0),
		"department_name": course_doc.get("department_name", ""),
		"exam_plan":       assignment.get("exam_plan", ""),
		"exam_name":       assignment.get("exam_name", ""),
		"evaluation_schema": assignment.get("evaluation_schema", ""),
		"grade_schema":    assignment.get("grade_schema", ""),
		"student_count":   count_row[0]["cnt"] if count_row else 0,
		"view_access":     int(access.get("view_access", 1)),
		"edit_access":     int(access.get("edit_access", 1)),
		"edit_deadline":   edit_deadline,
		"mask_student_info": int(access.get("mask_student_info", 0)),
		"status":          access.get("status", "UNLOCKED"),
		"columns":         columns,
		"reexam_columns":  reexam_columns,
	}


@frappe.whitelist()
def get_course_students_paged(course, search="", page=1, page_length=20,
                               sort_by="registration_id", sort_order="asc"):
	"""Return paginated students from Student Course Marks for a course."""
	page        = int(page)
	page_length = int(page_length)
	offset      = (page - 1) * page_length

	# Find exam plan for this course
	assignment = frappe.db.sql(
		"""
		SELECT csa.exam_plan
		FROM `tabCourse Schema Assignment` csa
		JOIN `tabExam Plan` ep ON ep.name = csa.exam_plan
		WHERE csa.course = %(course)s
		ORDER BY FIELD(ep.status, 'Active', 'Inactive') ASC, ep.creation DESC
		LIMIT 1
		""",
		{"course": course},
		as_dict=True,
	)
	exam_plan = assignment[0]["exam_plan"] if assignment else ""

	sort_col = (
		"sm.registration_id"
		if sort_by == "registration_id"
		else "CONCAT_WS(' ', sm.first_name, sm.last_name)"
	)
	sort_dir = "DESC" if sort_order == "desc" else "ASC"

	search_cond = ""
	params = {"course": course, "exam_plan": exam_plan, "lim": page_length, "off": offset}
	if search:
		search_cond = (
			"AND (sm.registration_id LIKE %(search)s "
			"OR sm.first_name LIKE %(search)s "
			"OR sm.last_name LIKE %(search)s)"
		)
		params["search"] = f"%{search}%"

	students = frappe.db.sql(
		f"""
		SELECT DISTINCT
			sm.name               AS student,
			sm.registration_id,
			CONCAT_WS(' ', sm.first_name, sm.last_name) AS student_name,
			sm.student_status,
			sm.account_status,
			sm.programme,
			sm.batch_year,
			sm.intake,
			sm.department,
			NULL AS section
		FROM `tabStudent Course Marks` scm
		LEFT JOIN `tabStudent Master` sm ON sm.name = scm.student
		WHERE scm.course = %(course)s
		  AND scm.exam_plan = %(exam_plan)s
		{search_cond}
		ORDER BY {sort_col} {sort_dir}
		LIMIT %(lim)s OFFSET %(off)s
		""",
		params,
		as_dict=True,
	)

	total_row = frappe.db.sql(
		f"""
		SELECT COUNT(DISTINCT scm.student) AS cnt
		FROM `tabStudent Course Marks` scm
		LEFT JOIN `tabStudent Master` sm ON sm.name = scm.student
		WHERE scm.course = %(course)s
		  AND scm.exam_plan = %(exam_plan)s
		{search_cond}
		""",
		params,
		as_dict=True,
	)

	return {
		"students": students,
		"total":    total_row[0]["cnt"] if total_row else 0,
	}


@frappe.whitelist()
def sync_students_from_enrollment(course):
	"""Create Student Course Marks records for all students enrolled in this course via Student Enrollment."""
	# Get the active exam plan and evaluation schema for the course
	assignment = frappe.db.sql(
		"""
		SELECT csa.exam_plan, csa.evaluation_schema
		FROM `tabCourse Schema Assignment` csa
		JOIN `tabExam Plan` ep ON ep.name = csa.exam_plan
		WHERE csa.course = %(course)s
		ORDER BY FIELD(ep.status, 'Active', 'Inactive') ASC, ep.creation DESC
		LIMIT 1
		""",
		{"course": course},
		as_dict=True,
	)
	if not assignment:
		frappe.throw("No Exam Plan assigned for this course. Please set up a Course Schema Assignment first.")

	exam_plan         = assignment[0]["exam_plan"]
	evaluation_schema = assignment[0]["evaluation_schema"] or ""

	# Find students enrolled in this course via Student Enrollment
	enrolled_students = frappe.db.sql(
		"""
		SELECT DISTINCT se.student
		FROM `tabStudent Enrollment` se
		INNER JOIN `tabProgram Enrollment` pe ON pe.parent = se.name
		WHERE pe.course = %(course)s
		  AND se.status = 'Enrolled'
		  AND se.student IS NOT NULL
		  AND se.student != ''
		""",
		{"course": course},
		as_dict=True,
	)

	if not enrolled_students:
		frappe.throw("No enrolled students found for this course in Student Enrollment.")

	added = 0
	skipped = 0
	for row in enrolled_students:
		student = row["student"]
		exists = frappe.db.exists("Student Course Marks", {
			"course":     course,
			"exam_plan":  exam_plan,
			"student":    student,
		})
		if exists:
			skipped += 1
			continue
		doc = frappe.new_doc("Student Course Marks")
		doc.course             = course
		doc.exam_plan          = exam_plan
		doc.student            = student
		doc.evaluation_schema  = evaluation_schema
		doc.status             = "Draft"
		doc.consider_for_sgpa  = 1
		doc.insert(ignore_permissions=True)
		added += 1

	frappe.db.commit()
	return {"added": added, "skipped": skipped, "total": len(enrolled_students)}


@frappe.whitelist()
def sync_students_from_class_config(course, class_config, course_type):
	"""Create Student Course Marks records for all students in the given Class Configuration."""
	# Validate the class config belongs to this course
	cc_course = frappe.db.get_value("Class Configuration", class_config, "course")
	if cc_course != course:
		frappe.throw("The selected Class does not belong to this course.")

	# Get active exam plan and evaluation schema
	assignment = frappe.db.sql(
		"""
		SELECT csa.exam_plan, csa.evaluation_schema
		FROM `tabCourse Schema Assignment` csa
		JOIN `tabExam Plan` ep ON ep.name = csa.exam_plan
		WHERE csa.course = %(course)s
		ORDER BY FIELD(ep.status, 'Active', 'Inactive') ASC, ep.creation DESC
		LIMIT 1
		""",
		{"course": course},
		as_dict=True,
	)
	if not assignment:
		frappe.throw("No Exam Plan assigned for this course. Please set up a Course Schema Assignment first.")

	exam_plan         = assignment[0]["exam_plan"]
	evaluation_schema = assignment[0]["evaluation_schema"] or ""

	# Get all students from the Class Configuration
	class_students = frappe.db.sql(
		"""
		SELECT cs.student
		FROM `tabClass Student` cs
		WHERE cs.parent = %(class_config)s
		  AND cs.student IS NOT NULL
		  AND cs.student != ''
		""",
		{"class_config": class_config},
		as_dict=True,
	)

	if not class_students:
		frappe.throw("No students found in the selected Class Configuration.")

	added = 0
	skipped = 0
	for row in class_students:
		student = row["student"]
		exists = frappe.db.exists("Student Course Marks", {
			"course":    course,
			"exam_plan": exam_plan,
			"student":   student,
		})
		if exists:
			skipped += 1
			continue
		doc = frappe.new_doc("Student Course Marks")
		doc.course            = course
		doc.exam_plan         = exam_plan
		doc.student           = student
		doc.evaluation_schema = evaluation_schema
		doc.status            = "Draft"
		doc.consider_for_sgpa = 1
		doc.insert(ignore_permissions=True)
		added += 1

		# Update course_type in Program Enrollment if present
		pe = frappe.db.get_value(
			"Program Enrollment",
			{"parent": ["like", "%"], "course": course, "parenttype": "Student Enrollment"},
			"name",
		)
		# Find program enrollment rows for this student and course
		pe_rows = frappe.db.sql(
			"""
			SELECT pe.name
			FROM `tabProgram Enrollment` pe
			INNER JOIN `tabStudent Enrollment` se ON se.name = pe.parent
			WHERE pe.course = %(course)s AND se.student = %(student)s
			LIMIT 1
			""",
			{"course": course, "student": student},
			as_dict=True,
		)
		if pe_rows and course_type:
			frappe.db.set_value("Program Enrollment", pe_rows[0]["name"], "course_type", course_type)

	frappe.db.commit()
	return {"added": added, "skipped": skipped, "total": len(class_students)}


@frappe.whitelist()
def get_student_hover_info(student, course):
	"""Return student profile + section for the hover popup."""
	sm = frappe.db.get_value(
		"Student Master", student,
		["registration_id", "first_name", "last_name",
		 "official_email_id", "email", "programme", "batch_year", "intake"],
		as_dict=True,
	)
	if not sm:
		return {}

	cohort_name = ""
	if sm.get("programme"):
		cohort_name = (
			frappe.db.get_value("Cohort", sm["programme"], "cohort_name")
			or sm["programme"]
		)

	section_row = frappe.db.sql(
		"""
		SELECT cc.section
		FROM `tabClass Student` cs
		INNER JOIN `tabClass Configuration` cc ON cs.parent = cc.name
		WHERE cs.student = %(student)s AND cc.course = %(course)s
		LIMIT 1
		""",
		{"student": student, "course": course},
		as_dict=True,
	)

	return {
		"student_name":    " ".join(filter(None, [sm.first_name, sm.last_name])),
		"registration_id": sm.registration_id or student,
		"email":           sm.official_email_id or sm.email or "",
		"programme":       cohort_name,
		"batch":           sm.batch_year or "",
		"intake":          sm.intake or "",
		"section":         section_row[0]["section"] if section_row else "",
	}


@frappe.whitelist()
def get_marks_for_students(course, exam_plan, student_ids):
	"""Return marks data keyed by student → {entries: {comp|atype → marks}, totals, status fields}."""
	import json as _json
	if isinstance(student_ids, str):
		student_ids = _json.loads(student_ids)
	if not student_ids or not exam_plan:
		return {}

	# Fetch header-level data (totals, grade, status fields)
	header_rows = frappe.db.sql(
		"""
		SELECT scm.student, scm.total_marks, scm.grade, scm.moderated_grade,
		       scm.status, scm.enrollment_status, scm.attendance_status,
		       scm.fairness_status, scm.consider_for_sgpa, scm.remark,
		       scm.updated_final_marks, scm.updated_grade
		FROM `tabStudent Course Marks` scm
		WHERE scm.course = %(course)s
		  AND scm.exam_plan = %(exam_plan)s
		  AND scm.student IN %(students)s
		""",
		{"course": course, "exam_plan": exam_plan, "students": tuple(student_ids)},
		as_dict=True,
	)

	result = {}
	for row in header_rows:
		s = row["student"]
		result[s] = {
			"total":               row["total_marks"],
			"grade":               row["grade"] or "",
			"moderated_grade":     row["moderated_grade"] or "",
			"status":              row["status"] or "",
			"enrollment_status":   row["enrollment_status"] or "",
			"attendance_status":   row["attendance_status"] or "",
			"fairness_status":     row["fairness_status"] or "",
			"consider_for_sgpa":   int(row["consider_for_sgpa"] or 0),
			"remark":              row["remark"] or "",
			"updated_final_marks": row["updated_final_marks"],
			"updated_grade":       row["updated_grade"] or "",
			"entries":             {},
		}

	# Fetch per-assessment marks
	entry_rows = frappe.db.sql(
		"""
		SELECT scm.student, sme.component, sme.assessment_type,
		       sme.marks, sme.revaluation_marks, sme.moderated_marks
		FROM `tabStudent Course Marks` scm
		JOIN `tabStudent Marks Entry` sme ON sme.parent = scm.name
		WHERE scm.course = %(course)s
		  AND scm.exam_plan = %(exam_plan)s
		  AND scm.student IN %(students)s
		""",
		{"course": course, "exam_plan": exam_plan, "students": tuple(student_ids)},
		as_dict=True,
	)

	for row in entry_rows:
		s = row["student"]
		if s not in result:
			result[s] = {"total": None, "grade": "", "moderated_grade": "",
			             "status": "", "enrollment_status": "", "attendance_status": "",
			             "fairness_status": "", "consider_for_sgpa": 1, "remark": "",
			             "updated_final_marks": None, "updated_grade": "", "entries": {}}
		key = (row["component"] or "") + "|" + (row["assessment_type"] or "")
		result[s]["entries"][key] = {
			"marks":             row["marks"],
			"revaluation_marks": row["revaluation_marks"],
			"moderated_marks":   row["moderated_marks"],
		}

	return result


@frappe.whitelist()
def get_course_overview(exam_plan, course):
	"""Return course info panel data for the Course Results page."""
	course_doc = frappe.db.get_value(
		"Course",
		course,
		["course_name", "course_code", "credit_value", "department_name"],
		as_dict=True,
	) or {}

	schema = frappe.db.get_value(
		"Course Schema Assignment",
		{"exam_plan": exam_plan, "course": course},
		["evaluation_schema", "grade_schema"],
		as_dict=True,
	) or {}

	access = frappe.db.get_value(
		"Course Result Access",
		{"exam_plan": exam_plan, "course": course},
		["view_access", "edit_access", "mask_student_info", "status",
		 "auto_generate_grade_access", "edit_grade_access"],
		as_dict=True,
	) or {}

	count_row = frappe.db.sql(
		"""
		SELECT COUNT(DISTINCT cs.student) AS cnt
		FROM `tabClass Student` cs
		INNER JOIN `tabClass Configuration` cc ON cs.parent = cc.name
		WHERE cc.course = %(course)s
		""",
		{"course": course},
		as_dict=True,
	)

	return {
		"course_name":              course_doc.get("course_name", ""),
		"course_code":              course_doc.get("course_code", ""),
		"credit_value":             course_doc.get("credit_value", 0),
		"department_name":          course_doc.get("department_name", ""),
		"evaluation_schema":        schema.get("evaluation_schema", ""),
		"grade_schema":             schema.get("grade_schema", ""),
		"view_access":              int(access.get("view_access", 1)),
		"edit_access":              int(access.get("edit_access", 1)),
		"mask_student_info":        int(access.get("mask_student_info", 0)),
		"auto_generate_grade_access": int(access.get("auto_generate_grade_access", 0)),
		"edit_grade_access":        int(access.get("edit_grade_access", 0)),
		"status":                   access.get("status", "UNLOCKED"),
		"student_count":            (count_row[0]["cnt"] if count_row else 0),
	}


@frappe.whitelist()
def get_course_students_with_marks(exam_plan, course, search="", page=1, page_length=20):
	"""
	Return paginated students enrolled in the course via Class Configuration,
	along with placeholder marks structure per exam type.
	"""
	page        = int(page)
	page_length = int(page_length)
	offset      = (page - 1) * page_length

	search_cond = ""
	params      = {"course": course, "lim": page_length, "off": offset}

	if search:
		search_cond    = "AND (sm.registration_id LIKE %(search)s OR sm.first_name LIKE %(search)s OR sm.last_name LIKE %(search)s)"
		params["search"] = f"%{search}%"

	students = frappe.db.sql(
		f"""
		SELECT DISTINCT
			sm.name           AS student,
			sm.registration_id,
			CONCAT_WS(' ', sm.first_name, sm.last_name) AS student_name,
			sm.email,
			sm.official_email_id,
			sm.student_status,
			sm.account_status,
			sm.programme,
			sm.batch_year,
			sm.intake,
			sm.department
		FROM `tabClass Student` cs
		INNER JOIN `tabClass Configuration` cc ON cs.parent = cc.name
		LEFT JOIN `tabStudent Master` sm ON sm.name = cs.student
		WHERE cc.course = %(course)s
		{search_cond}
		ORDER BY sm.registration_id ASC
		LIMIT %(lim)s OFFSET %(off)s
		""",
		params,
		as_dict=True,
	)

	total_row = frappe.db.sql(
		f"""
		SELECT COUNT(DISTINCT cs.student) AS cnt
		FROM `tabClass Student` cs
		INNER JOIN `tabClass Configuration` cc ON cs.parent = cc.name
		LEFT JOIN `tabStudent Master` sm ON sm.name = cs.student
		WHERE cc.course = %(course)s
		{search_cond}
		""",
		params,
		as_dict=True,
	)

	# Exam types visible for this course (from Result Exam Visibility)
	visible_types = frappe.db.sql(
		"""
		SELECT rev.exam_type, eat.type_name
		FROM `tabResult Exam Visibility` rev
		INNER JOIN `tabCourse Result Access` cra ON rev.parent = cra.name
		LEFT JOIN `tabExam Assessment Type` eat ON eat.name = rev.exam_type
		WHERE cra.exam_plan = %(exam_plan)s AND cra.course = %(course)s
		""",
		{"exam_plan": exam_plan, "course": course},
		as_dict=True,
	)

	return {
		"students":      students,
		"total":         (total_row[0]["cnt"] if total_row else 0),
		"page":          page,
		"page_length":   page_length,
		"exam_types":    visible_types,
	}


@frappe.whitelist()
def get_student_profile(student):
	"""Return detailed student info for hover popup on Course Results page."""
	sm = frappe.db.get_value(
		"Student Master",
		student,
		["registration_id", "first_name", "last_name", "email", "official_email_id",
		 "programme", "batch_year", "intake", "student_status", "account_status",
		 "phone", "department"],
		as_dict=True,
	)
	if not sm:
		frappe.throw("Student not found.")
	# Get cohort/programme label
	cohort_name = ""
	if sm.get("programme"):
		cohort_name = frappe.db.get_value("Cohort", sm["programme"], "cohort_name") or sm["programme"]
	sm["cohort_name"] = cohort_name
	return sm


@frappe.whitelist()
def get_calc_settings(evaluation_schema):
	"""Return calculation settings for the evaluation schema."""
	doc = frappe.db.get_value(
		"Evaluation Schema",
		evaluation_schema,
		["calc_higher_revaluation", "calc_higher_makeup", "calc_higher_reexam"],
		as_dict=True,
	) or {}
	return {
		"calc_higher_revaluation": int(doc.get("calc_higher_revaluation") or 0),
		"calc_higher_makeup":      int(doc.get("calc_higher_makeup") or 0),
		"calc_higher_reexam":      int(doc.get("calc_higher_reexam") or 0),
	}


@frappe.whitelist()
def save_calc_settings(evaluation_schema, calc_higher_revaluation, calc_higher_makeup, calc_higher_reexam):
	"""Save calculation settings to the evaluation schema."""
	doc = frappe.get_doc("Evaluation Schema", evaluation_schema)
	doc.calc_higher_revaluation = int(calc_higher_revaluation)
	doc.calc_higher_makeup      = int(calc_higher_makeup)
	doc.calc_higher_reexam      = int(calc_higher_reexam)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return True


@frappe.whitelist()
def get_evaluation_schema_details(name):
	"""Return full evaluation schema for the popup view."""
	doc = frappe.get_doc("Evaluation Schema", name)

	components = []
	for row in doc.schema_components:
		comp_name = frappe.db.get_value("Exam Component", row.component, "component_name") or row.component
		components.append({
			"component":       row.component,
			"component_name":  comp_name,
			"effective_max_marks": row.effective_max_marks,
			"weightage":       row.weightage,
			"passing_marks":   row.passing_marks,
			"consider_for_pass_fail": int(row.consider_for_pass_fail or 0),
		})

	assessments = []
	for row in doc.assessment_configs:
		comp_name = frappe.db.get_value("Exam Component", row.component, "component_name") or row.component
		type_name = frappe.db.get_value("Exam Assessment Type", row.assessment_type, "type_name") or row.assessment_type
		assessments.append({
			"component":       row.component,
			"component_name":  comp_name,
			"assessment_type": row.assessment_type,
			"type_name":       type_name,
			"label":           row.label,
			"maximum_marks":   row.maximum_marks,
			"effective_marks": row.effective_marks,
			"passing_marks":   row.passing_marks,
			"consider_for_pass_fail": int(row.consider_for_pass_fail or 0),
			"enrollment":      row.enrollment,
		})

	return {
		"schema_name":   doc.schema_name,
		"description":   doc.description or "",
		"total_marks":   doc.total_marks,
		"passing_marks": doc.passing_marks,
		"components":    components,
		"assessments":   assessments,
		"calc_higher_revaluation": int(doc.calc_higher_revaluation or 0),
		"calc_higher_makeup":      int(doc.calc_higher_makeup or 0),
		"calc_higher_reexam":      int(doc.calc_higher_reexam or 0),
	}


@frappe.whitelist()
def get_grading_schema_details(name):
	"""Return full grading schema for the popup view."""
	doc = frappe.get_doc("Grading Schema", name)

	grades = []
	for row in doc.grades:
		grades.append({
			"grade":               row.grade,
			"qualitative_meaning": row.qualitative_meaning or "",
			"from_operator":       row.from_operator or ">=",
			"marks_from":          row.marks_from,
			"to_operator":         row.to_operator or "<",
			"marks_to":            row.marks_to,
			"grade_point":         row.grade_point,
			"failed":              int(row.failed or 0),
			"consider_for_sgpa":   int(row.consider_for_sgpa or 0),
		})

	return {
		"grading_schema_name": doc.grading_schema_name,
		"schema_name":         doc.schema_name or "",
		"description":         doc.description or "",
		"maximum_marks":       doc.maximum_marks,
		"grading_type":        doc.grading_type,
		"grades":              grades,
	}


@frappe.whitelist()
def get_result_summary(exam_plan):
	"""Return high-level counts for the result settings dashboard."""
	total      = frappe.db.count("Course", {})
	configured = frappe.db.count("Course Result Access", {"exam_plan": exam_plan})
	locked     = frappe.db.count("Course Result Access", {"exam_plan": exam_plan, "status": "LOCKED"})
	unlocked   = configured - locked
	return {
		"total_courses": total,
		"configured":    configured,
		"locked":        locked,
		"unlocked":      unlocked,
		"unconfigured":  total - configured,
	}


@frappe.whitelist()
def download_grade_sample(course, exam_plan, include_students=1):
	"""Generate a sample Excel file for bulk grade upload."""
	import io
	try:
		import openpyxl
		from openpyxl.styles import Font, PatternFill, Alignment
	except ImportError:
		frappe.throw("openpyxl is required. Run: bench pip install openpyxl")

	include_students = frappe.utils.cint(include_students)

	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "Grade Upload"

	header_font  = Font(bold=True, color="FFFFFF")
	header_fill  = PatternFill("solid", fgColor="C0392B")
	center_align = Alignment(horizontal="center")

	headers = ["Registration ID", "Email ID", "Student Name", "Grade"]
	for col, h in enumerate(headers, 1):
		cell = ws.cell(row=1, column=col, value=h)
		cell.font  = header_font
		cell.fill  = header_fill
		cell.alignment = center_align

	ws.column_dimensions["A"].width = 20
	ws.column_dimensions["B"].width = 30
	ws.column_dimensions["C"].width = 30
	ws.column_dimensions["D"].width = 15

	if include_students:
		students = frappe.db.sql(
			"""
			SELECT sm.registration_id, sm.official_email_id,
			       CONCAT_WS(' ', sm.first_name, sm.last_name) AS student_name
			FROM `tabStudent Course Marks` scm
			LEFT JOIN `tabStudent Master` sm ON sm.name = scm.student
			WHERE scm.course = %(course)s AND scm.exam_plan = %(exam_plan)s
			ORDER BY sm.registration_id ASC
			""",
			{"course": course, "exam_plan": exam_plan},
			as_dict=True,
		)
		for row_idx, s in enumerate(students, 2):
			ws.cell(row=row_idx, column=1, value=s.registration_id or "")
			ws.cell(row=row_idx, column=2, value=s.official_email_id or "")
			ws.cell(row=row_idx, column=3, value=s.student_name or "")
			ws.cell(row=row_idx, column=4, value="")

	buf = io.BytesIO()
	wb.save(buf)
	buf.seek(0)

	file_name = f"grade_upload_{course}.xlsx"
	file_doc = frappe.get_doc({
		"doctype":    "File",
		"file_name":  file_name,
		"is_private": 1,
		"content":    buf.read(),
	})
	file_doc.save(ignore_permissions=True)
	return {"file_url": file_doc.file_url}


@frappe.whitelist()
def bulk_upload_grades(course, exam_plan, file_url):
	"""Process uploaded Excel file and update grades in Student Course Marks."""
	import io
	try:
		import openpyxl
	except ImportError:
		frappe.throw("openpyxl is required. Run: bench pip install openpyxl")

	# Fetch the file
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	file_path = file_doc.get_full_path()

	wb = openpyxl.load_workbook(file_path, data_only=True)
	ws = wb.active

	headers = [str(ws.cell(1, c).value or "").strip() for c in range(1, ws.max_column + 1)]

	def col_idx(name):
		try:
			return headers.index(name)
		except ValueError:
			return -1

	reg_col   = col_idx("Registration ID")
	email_col = col_idx("Email ID")
	grade_col = col_idx("Grade")

	if grade_col == -1:
		frappe.throw("Column 'Grade' not found in the uploaded file.")

	updated = 0
	errors  = []

	for row in ws.iter_rows(min_row=2, values_only=True):
		reg_id = str(row[reg_col]).strip() if reg_col >= 0 and row[reg_col] else ""
		email  = str(row[email_col]).strip() if email_col >= 0 and row[email_col] else ""
		grade  = str(row[grade_col]).strip() if row[grade_col] else ""

		if not grade:
			continue

		# Find student
		student = None
		if reg_id:
			student = frappe.db.get_value("Student Master", {"registration_id": reg_id}, "name")
		if not student and email:
			student = frappe.db.get_value(
				"Student Master",
				[["official_email_id", "=", email], ["email", "=", email]],
				"name",
				or_filters=True,
			) or frappe.db.get_value("Student Master", {"official_email_id": email}, "name") \
			  or frappe.db.get_value("Student Master", {"email": email}, "name")

		if not student:
			errors.append(f"Student not found: {reg_id or email}")
			continue

		scm_name = frappe.db.get_value(
			"Student Course Marks",
			{"course": course, "exam_plan": exam_plan, "student": student},
			"name",
		)
		if not scm_name:
			errors.append(f"No result record for: {reg_id or email}")
			continue

		frappe.db.set_value("Student Course Marks", scm_name, "grade", grade)
		updated += 1

	frappe.db.commit()
	return {"updated": updated, "errors": errors}
