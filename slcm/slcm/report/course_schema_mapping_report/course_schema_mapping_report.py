# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": "Exam Plan",
			"fieldname": "exam_plan",
			"fieldtype": "Link",
			"options": "Exam Plan",
			"width": 180,
		},
		{
			"label": "Term",
			"fieldname": "term",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": "Course Code",
			"fieldname": "course_code",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": "Course Name",
			"fieldname": "course_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": "Department",
			"fieldname": "department_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "Credits",
			"fieldname": "credit_value",
			"fieldtype": "Float",
			"width": 75,
		},
		{
			"label": "Evaluation Schema",
			"fieldname": "evaluation_schema",
			"fieldtype": "Link",
			"options": "Evaluation Schema",
			"width": 180,
		},
		{
			"label": "Max Marks",
			"fieldname": "max_marks",
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"label": "Grade Schema",
			"fieldname": "grade_schema",
			"fieldtype": "Link",
			"options": "Grading Schema",
			"width": 180,
		},
		{
			"label": "Mapping Status",
			"fieldname": "mapping_status",
			"fieldtype": "Data",
			"width": 130,
		},
	]


def get_data(filters):
	exam_plan_filter  = filters.get("exam_plan")
	status_filter     = filters.get("mapping_status")
	search            = filters.get("search") or ""

	# ── 1. Load exam plan → term map ──────────────────────────────────────
	ep_rows = frappe.db.sql(
		"SELECT name, term FROM `tabExam Plan`",
		as_dict=True,
	)
	ep_term = {r["name"]: (r["term"] or "") for r in ep_rows}

	# ── 2. Fetch assignments ──────────────────────────────────────────────
	if exam_plan_filter:
		asgn_rows = frappe.db.sql(
			"""
			SELECT exam_plan, course, evaluation_schema, grade_schema
			FROM `tabCourse Schema Assignment`
			WHERE exam_plan = %(ep)s
			""",
			{"ep": exam_plan_filter},
			as_dict=True,
		)
	else:
		asgn_rows = frappe.db.sql(
			"""
			SELECT exam_plan, course, evaluation_schema, grade_schema
			FROM `tabCourse Schema Assignment`
			""",
			as_dict=True,
		)

	# course → list of assignment rows (a course can be in multiple plans)
	from collections import defaultdict
	asgn_map = defaultdict(list)
	for r in asgn_rows:
		asgn_map[r["course"]].append(r)

	# ── 3. Fetch courses ──────────────────────────────────────────────────
	search_cond = ""
	values = {}
	if search:
		search_cond = "WHERE course_name LIKE %(s)s OR course_code LIKE %(s)s"
		values["s"] = f"%{search}%"

	courses = frappe.db.sql(
		f"""
		SELECT name, course_code, course_name, department_name, credit_value
		FROM `tabCourse`
		{search_cond}
		ORDER BY course_name ASC
		""",
		values,
		as_dict=True,
	)

	# ── 4. Cache max_marks per evaluation schema ──────────────────────────
	schema_marks = {}

	# ── 5. Build rows ─────────────────────────────────────────────────────
	data = []
	for c in courses:
		assignments = asgn_map.get(c["name"], [])

		if assignments:
			# One output row per (course × exam plan) assignment
			for asgn in assignments:
				ev = asgn.get("evaluation_schema") or ""
				gr = asgn.get("grade_schema") or ""
				ep = asgn.get("exam_plan") or ""

				status = "Fully Mapped" if (ev and gr) else "Partially Mapped"

				if status_filter and status != status_filter:
					continue

				if ev:
					if ev not in schema_marks:
						schema_marks[ev] = (
							frappe.db.get_value("Evaluation Schema", ev, "total_marks") or ""
						)
					max_marks = schema_marks[ev]
				else:
					max_marks = ""

				data.append({
					"exam_plan":       ep,
					"term":            ep_term.get(ep, ""),
					"course_code":     c.get("course_code") or "",
					"course_name":     c.get("course_name") or c.get("name"),
					"department_name": c.get("department_name") or "",
					"credit_value":    c.get("credit_value") or 0,
					"evaluation_schema": ev or None,
					"max_marks":       max_marks,
					"grade_schema":    gr or None,
					"mapping_status":  status,
				})
		else:
			# Course has no assignment — only show if status_filter allows it
			if status_filter and status_filter != "Not Mapped":
				continue

			# When an exam_plan is selected show the plan; otherwise leave blank
			data.append({
				"exam_plan":       exam_plan_filter or "",
				"term":            ep_term.get(exam_plan_filter, "") if exam_plan_filter else "",
				"course_code":     c.get("course_code") or "",
				"course_name":     c.get("course_name") or c.get("name"),
				"department_name": c.get("department_name") or "",
				"credit_value":    c.get("credit_value") or 0,
				"evaluation_schema": None,
				"max_marks":       "",
				"grade_schema":    None,
				"mapping_status":  "Not Mapped",
			})

	return data


def get_filters():
	return [
		{
			"fieldname": "exam_plan",
			"label": "Exam Plan",
			"fieldtype": "Link",
			"options": "Exam Plan",
			"reqd": 0,
		},
		{
			"fieldname": "mapping_status",
			"label": "Mapping Status",
			"fieldtype": "Select",
			"options": "\nFully Mapped\nPartially Mapped\nNot Mapped",
		},
		{
			"fieldname": "search",
			"label": "Search Course",
			"fieldtype": "Data",
		},
	]
