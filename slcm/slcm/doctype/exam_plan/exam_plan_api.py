# Copyright (c) 2026, CU and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist()
def get_exam_plans(search=None):
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
def create_exam_plan(exam_name, term):
	if frappe.db.exists("Exam Plan", exam_name):
		frappe.throw(f"Exam Plan '{exam_name}' already exists.")
	doc = frappe.new_doc("Exam Plan")
	doc.exam_name = exam_name
	doc.term = term
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "exam_name": doc.exam_name, "term": doc.term, "status": doc.status}


@frappe.whitelist()
def get_components(search=None):
	filters = {}
	if search:
		filters["component_name"] = ["like", f"%{search}%"]
	return frappe.get_all(
		"Exam Component",
		filters=filters,
		fields=["name", "component_name", "component_type", "is_active"],
		order_by="creation desc",
	)


@frappe.whitelist()
def save_component(component_name, component_type, name=None):
	if name and frappe.db.exists("Exam Component", name):
		doc = frappe.get_doc("Exam Component", name)
		doc.component_name = component_name
		doc.component_type = component_type
		doc.save(ignore_permissions=True)
	else:
		if frappe.db.exists("Exam Component", component_name):
			frappe.throw(f"Component '{component_name}' already exists.")
		doc = frappe.new_doc("Exam Component")
		doc.component_name = component_name
		doc.component_type = component_type
		doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {
		"name": doc.name,
		"component_name": doc.component_name,
		"component_type": doc.component_type,
		"is_active": doc.is_active,
	}


@frappe.whitelist()
def get_assessment_types(search=None):
	filters = {}
	if search:
		filters["type_name"] = ["like", f"%{search}%"]
	return frappe.get_all(
		"Exam Assessment Type",
		filters=filters,
		fields=["name", "type_name", "assessment_type", "is_active"],
		order_by="creation desc",
	)


@frappe.whitelist()
def save_assessment_type(type_name, assessment_type, name=None):
	if name and frappe.db.exists("Exam Assessment Type", name):
		doc = frappe.get_doc("Exam Assessment Type", name)
		doc.type_name = type_name
		doc.assessment_type = assessment_type
		doc.save(ignore_permissions=True)
	else:
		if frappe.db.exists("Exam Assessment Type", type_name):
			frappe.throw(f"Assessment Type '{type_name}' already exists.")
		doc = frappe.new_doc("Exam Assessment Type")
		doc.type_name = type_name
		doc.assessment_type = assessment_type
		doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {
		"name": doc.name,
		"type_name": doc.type_name,
		"assessment_type": doc.assessment_type,
		"is_active": doc.is_active,
	}


@frappe.whitelist()
def get_schemas(search=None):
	filters = {}
	if search:
		filters["schema_name"] = ["like", f"%{search}%"]
	schemas = frappe.get_all(
		"Evaluation Schema",
		filters=filters,
		fields=["name", "schema_name", "description", "total_marks", "passing_marks"],
		order_by="creation desc",
	)
	for schema in schemas:
		schema["assigned_courses"] = frappe.db.count(
			"Course Schema Assignment", {"evaluation_schema": schema["name"]}
		) if frappe.db.table_exists("tabCourse Schema Assignment") else 0
	return schemas


@frappe.whitelist()
def get_schema_detail(name):
	if not frappe.db.exists("Evaluation Schema", name):
		frappe.throw(f"Schema '{name}' not found.")
	doc = frappe.get_doc("Evaluation Schema", name)
	components = []
	for c in doc.schema_components:
		comp_type = frappe.db.get_value("Exam Component", c.component, "component_type") or "Custom"
		components.append(
			{
				"name": c.name,
				"component": c.component,
				"component_type": comp_type,
				"label": c.label,
				"effective_max_marks": c.effective_max_marks,
				"weightage": c.weightage,
				"passing_marks": c.passing_marks,
				"consider_for_pass_fail": c.consider_for_pass_fail,
			}
		)
	assessment_configs = []
	for a in doc.assessment_configs:
		at_type = frappe.db.get_value("Exam Assessment Type", a.assessment_type, "assessment_type") or "Assessment"
		assessment_configs.append(
			{
				"name": a.name,
				"component": a.component,
				"assessment_type": a.assessment_type,
				"assessment_type_category": at_type,
				"label": a.label,
				"effective_marks": a.effective_marks,
				"maximum_marks": a.maximum_marks,
				"minimum_marks": a.minimum_marks,
				"passing_marks": a.passing_marks,
				"consider_for_pass_fail": a.consider_for_pass_fail,
				"weightage": a.weightage,
				"enrollment": a.enrollment,
			}
		)
	reexam_configs = []
	for r in doc.reexam_configs:
		reexam_configs.append(
			{
				"name": r.name,
				"component": r.component,
				"re_exam_type_category": r.re_exam_type_category,
				"assessment_type": r.assessment_type,
				"label": r.label,
				"maximum_marks": r.maximum_marks,
				"minimum_marks": r.minimum_marks,
				"passing_marks": r.passing_marks,
				"enrollment": r.enrollment,
				"substitute_for": r.substitute_for,
				"substitute_weightage": r.substitute_weightage,
				"effective_marks": r.effective_marks,
			}
		)
	return {
		"name": doc.name,
		"schema_name": doc.schema_name,
		"description": doc.description,
		"total_marks": doc.total_marks,
		"passing_marks": doc.passing_marks,
		"schema_components": components,
		"assessment_configs": assessment_configs,
		"reexam_configs": reexam_configs,
	}


@frappe.whitelist()
def save_schema(data):
	import json

	if isinstance(data, str):
		data = json.loads(data)

	name = data.get("name")
	schema_name = data.get("schema_name")

	if name and frappe.db.exists("Evaluation Schema", name):
		doc = frappe.get_doc("Evaluation Schema", name)
	else:
		if frappe.db.exists("Evaluation Schema", schema_name):
			frappe.throw(f"Schema '{schema_name}' already exists.")
		doc = frappe.new_doc("Evaluation Schema")
		doc.schema_name = schema_name

	doc.description = data.get("description", "")
	doc.total_marks = data.get("total_marks", 100)
	doc.passing_marks = data.get("passing_marks", 0)

	doc.set("schema_components", [])
	for c in data.get("schema_components", []):
		doc.append(
			"schema_components",
			{
				"component": c.get("component"),
				"label": c.get("label", ""),
				"effective_max_marks": c.get("effective_max_marks", 0),
				"weightage": c.get("weightage", 100),
				"passing_marks": c.get("passing_marks", 0),
				"consider_for_pass_fail": c.get("consider_for_pass_fail", 0),
			},
		)

	doc.set("assessment_configs", [])
	for a in data.get("assessment_configs", []):
		doc.append(
			"assessment_configs",
			{
				"component": a.get("component"),
				"assessment_type": a.get("assessment_type"),
				"label": a.get("label", ""),
				"effective_marks": a.get("effective_marks", 0),
				"maximum_marks": a.get("maximum_marks", 0),
				"minimum_marks": a.get("minimum_marks", 0),
				"passing_marks": a.get("passing_marks", 0),
				"consider_for_pass_fail": a.get("consider_for_pass_fail", 0),
				"weightage": a.get("weightage", 100),
				"enrollment": a.get("enrollment", "Auto"),
			},
		)

	doc.set("reexam_configs", [])
	for r in data.get("reexam_configs", []):
		doc.append(
			"reexam_configs",
			{
				"component": r.get("component"),
				"re_exam_type_category": r.get("re_exam_type_category", "Assessment"),
				"assessment_type": r.get("assessment_type"),
				"label": r.get("label", ""),
				"maximum_marks": r.get("maximum_marks", 0),
				"minimum_marks": r.get("minimum_marks", 0),
				"passing_marks": r.get("passing_marks", 0),
				"enrollment": r.get("enrollment", "Manual"),
				"substitute_for": r.get("substitute_for"),
				"substitute_weightage": r.get("substitute_weightage", 100),
				"effective_marks": r.get("effective_marks", 0),
			},
		)

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "schema_name": doc.schema_name}


@frappe.whitelist()
def get_terms():
	return frappe.get_all(
		"Academic Term",
		fields=["name", "term_name"],
		order_by="creation desc",
	)


@frappe.whitelist()
def get_courses_for_plan(exam_plan, search=""):
	"""Return all courses with their schema assignments for the given exam plan."""
	if search:
		courses = frappe.db.sql(
			"""
			SELECT name, course_name, course_code, department_name, credit_value
			FROM `tabCourse`
			WHERE course_name LIKE %(s)s OR course_code LIKE %(s)s
			ORDER BY course_name ASC
			LIMIT 500
			""",
			{"s": f"%{search}%"},
			as_dict=True,
		)
	else:
		courses = frappe.get_all(
			"Course",
			fields=["name", "course_name", "course_code", "department_name", "credit_value"],
			order_by="course_name asc",
			page_length=500,
		)

	# Fetch existing assignments for this plan
	asgn_map = {}
	try:
		assignments = frappe.db.sql(
			"""
			SELECT name, course, evaluation_schema, grade_schema
			FROM `tabCourse Schema Assignment`
			WHERE exam_plan = %(exam_plan)s
			""",
			{"exam_plan": exam_plan},
			as_dict=True,
		)
		asgn_map = {a["course"]: a for a in assignments}
	except Exception:
		pass

	for c in courses:
		asgn = asgn_map.get(c["name"], {})
		c["evaluation_schema"] = asgn.get("evaluation_schema") or ""
		c["grade_schema"] = asgn.get("grade_schema") or ""
		c["assignment_name"] = asgn.get("name", "")
		if asgn.get("evaluation_schema"):
			c["max_marks"] = (
				frappe.db.get_value("Evaluation Schema", asgn["evaluation_schema"], "total_marks") or ""
			)
		else:
			c["max_marks"] = ""

	return courses


@frappe.whitelist()
def save_course_schema(exam_plan, assignments):
	"""Create or update Course Schema Assignment records."""
	import json

	_SKIP = "__SKIP__"

	if isinstance(assignments, str):
		assignments = json.loads(assignments)

	for asgn in assignments:
		course = asgn.get("course")
		if not course:
			continue

		eval_schema  = asgn.get("evaluation_schema", _SKIP)
		grade_schema = asgn.get("grade_schema",      _SKIP)

		rows = frappe.db.sql(
			"SELECT name FROM `tabCourse Schema Assignment` WHERE exam_plan=%s AND course=%s LIMIT 1",
			(exam_plan, course),
		)
		existing = rows[0][0] if rows else None

		if existing:
			update = {}
			if eval_schema  != _SKIP: update["evaluation_schema"] = eval_schema  or None
			if grade_schema != _SKIP: update["grade_schema"]      = grade_schema or None

			if update:
				cur_row = frappe.db.sql(
					"SELECT evaluation_schema, grade_schema FROM `tabCourse Schema Assignment` WHERE name=%s",
					(existing,), as_dict=True
				)
				cur = cur_row[0] if cur_row else frappe._dict()
				old_ev = cur.get("evaluation_schema")
				old_gr = cur.get("grade_schema")
				new_ev = update.get("evaluation_schema", old_ev)
				new_gr = update.get("grade_schema",      old_gr)
				if not new_ev and not new_gr:
					frappe.delete_doc("Course Schema Assignment", existing, ignore_permissions=True)
				else:
					frappe.db.sql(
						"""UPDATE `tabCourse Schema Assignment`
						   SET evaluation_schema=%s, grade_schema=%s, modified=NOW(), modified_by=%s
						   WHERE name=%s""",
						(new_ev, new_gr, frappe.session.user, existing)
					)
					if old_ev != new_ev or old_gr != new_gr:
						try:
							log = frappe.new_doc("Schema Change Log")
							log.exam_plan = exam_plan
							log.course = course
							log.old_evaluation_schema = old_ev or ""
							log.new_evaluation_schema = new_ev or ""
							log.old_grade_schema = old_gr or ""
							log.new_grade_schema = new_gr or ""
							log.changed_by = frappe.session.user
							log.changed_on = frappe.utils.now()
							log.insert(ignore_permissions=True)
						except Exception:
							pass
		else:
			ev = eval_schema  if eval_schema  != _SKIP else None
			gr = grade_schema if grade_schema != _SKIP else None
			if ev or gr:
				doc = frappe.new_doc("Course Schema Assignment")
				doc.exam_plan         = exam_plan
				doc.course            = course
				doc.evaluation_schema = ev
				doc.grade_schema      = gr
				doc.insert(ignore_permissions=True)

	frappe.db.commit()
	return True


@frappe.whitelist()
def unmap_course_schema(exam_plan, courses):
	"""Delete Course Schema Assignment records for the given courses."""
	import json

	if isinstance(courses, str):
		courses = json.loads(courses)

	for course in courses:
		rows = frappe.db.sql(
			"SELECT name FROM `tabCourse Schema Assignment` WHERE exam_plan=%s AND course=%s",
			(exam_plan, course),
		)
		for row in rows:
			frappe.delete_doc("Course Schema Assignment", row[0], ignore_permissions=True)

	frappe.db.commit()
	return True
