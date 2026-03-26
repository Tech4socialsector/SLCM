# Copyright (c) 2026, CU and contributors
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
			"label": "Course Code",
			"fieldname": "course_code",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": "Course Name",
			"fieldname": "course_name",
			"fieldtype": "Link",
			"options": "Course",
			"width": 220,
		},
		{
			"label": "Department",
			"fieldname": "department_name",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": "Credits",
			"fieldname": "credit_value",
			"fieldtype": "Float",
			"width": 80,
		},
		{
			"label": "Evaluation Schema",
			"fieldname": "evaluation_schema",
			"fieldtype": "Link",
			"options": "Evaluation Schema",
			"width": 200,
		},
		{
			"label": "Max Marks",
			"fieldname": "max_marks",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": "Grade Schema",
			"fieldname": "grade_schema",
			"fieldtype": "Link",
			"options": "Grading Schema",
			"width": 200,
		},
		{
			"label": "Mapping Status",
			"fieldname": "mapping_status",
			"fieldtype": "Data",
			"width": 130,
		},
	]


def get_data(filters):
	exam_plan = filters.get("exam_plan")
	mapping_status_filter = filters.get("mapping_status")
	search = filters.get("search") or ""

	# Base course query
	conditions = ""
	values = {}
	if search:
		conditions = "WHERE (c.course_name LIKE %(search)s OR c.course_code LIKE %(search)s)"
		values["search"] = f"%{search}%"

	courses = frappe.db.sql(
		f"""
		SELECT
			c.name,
			c.course_code,
			c.course_name,
			c.department_name,
			c.credit_value
		FROM `tabCourse` c
		{conditions}
		ORDER BY c.course_name ASC
		""",
		values,
		as_dict=True,
	)

	# Fetch schema assignments for this exam plan
	asgn_map = {}
	if exam_plan:
		try:
			rows = frappe.db.sql(
				"""
				SELECT course, evaluation_schema, grade_schema
				FROM `tabCourse Schema Assignment`
				WHERE exam_plan = %(ep)s
				""",
				{"ep": exam_plan},
				as_dict=True,
			)
			asgn_map = {r["course"]: r for r in rows}
		except Exception:
			pass

	# Build result rows
	data = []
	for c in courses:
		asgn = asgn_map.get(c["name"], {})
		ev = asgn.get("evaluation_schema") or ""
		gr = asgn.get("grade_schema") or ""

		if ev and gr:
			status = "Fully Mapped"
		elif ev or gr:
			status = "Partially Mapped"
		else:
			status = "Not Mapped"

		# Apply mapping_status filter
		if mapping_status_filter and status != mapping_status_filter:
			continue

		max_marks = ""
		if ev:
			max_marks = frappe.db.get_value("Evaluation Schema", ev, "total_marks") or ""

		data.append(
			{
				"course_code": c.get("course_code") or "",
				"course_name": c.get("name"),
				"department_name": c.get("department_name") or "",
				"credit_value": c.get("credit_value") or 0,
				"evaluation_schema": ev or None,
				"max_marks": max_marks,
				"grade_schema": gr or None,
				"mapping_status": status,
			}
		)

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
