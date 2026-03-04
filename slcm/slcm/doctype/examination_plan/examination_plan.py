# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json


class ExaminationPlan(Document):
	pass

@frappe.whitelist()
def update_exam_types(updates):
	if isinstance(updates, str):
		updates = json.loads(updates)
		
	for update in updates:
		if frappe.db.exists("Exam Type", update.get("name")):
			frappe.db.set_value("Exam Type", update.get("name"), "belongs_in_re_exam_component", update.get("belongs_in_re_exam_component"))
	frappe.db.commit()

@frappe.whitelist()
def update_exam_types(updates):
	if isinstance(updates, str):
		updates = json.loads(updates)
		
	for update in updates:
		if frappe.db.exists("Exam Type", update.get("name")):
			frappe.db.set_value("Exam Type", update.get("name"), "belongs_in_re_exam_component", update.get("belongs_in_re_exam_component"))
	frappe.db.commit()

@frappe.whitelist()
def get_exam_courses(exam_plan_name):
	plan = frappe.get_doc("Examination Plan", exam_plan_name)
	
	# Fetch all available courses (In a real scenario, this might be filtered by Program/Term)
	courses = frappe.get_all("Course", fields=["name", "course_name", "course_code", "course_type", "credit_value", "department_name"])
	
	for course in courses:
		mapped = frappe.db.get_value("Exam Course Mapping", {"examination_plan": exam_plan_name, "course": course.name}, ["name", "exam_schema", "grading_schema"], as_dict=True)
		if mapped:
			course["mapped_id"] = mapped.name
			
			course["evaluation_schema"] = mapped.exam_schema
			course["grade_schema"] = mapped.grading_schema

			if mapped.exam_schema:
				max_marks = frappe.db.get_value("Exam Schema", mapped.exam_schema, "total_marks")
				course["max_marks"] = max_marks
			else:
				course["max_marks"] = None
		else:
			course["mapped_id"] = None
			course["evaluation_schema"] = None
			course["grade_schema"] = None
			course["max_marks"] = None

		# Count enrolled students
		# (Note: In a strict setup, we might filter by `se.term_name = plan.academic_term`. For now, we fetch any enrollment for the course)
		enrolled = frappe.db.sql("""
			SELECT COUNT(sec.name) 
			FROM `tabProgram Enrollment` sec 
			JOIN `tabStudent Enrollment` se ON se.name = sec.parent 
			WHERE sec.course = %s
		""", (course.name,))
		course["enrolled_students"] = enrolled[0][0] if enrolled else 0
			
	return courses

@frappe.whitelist()
def get_course_students(exam_plan_name, course_names=None):
	plan = frappe.get_doc("Examination Plan", exam_plan_name)
	
	if isinstance(course_names, str):
		try:
			course_names = json.loads(course_names)
		except:
			course_names = [course_names]
	
	course_condition = ""
	args_tuple = []
	if course_names:
		format_strings = ','.join(['%s'] * len(course_names))
		course_condition = f"AND sec.course IN ({format_strings})"
		args_tuple = list(course_names)
		
	students = frappe.db.sql(f"""
		SELECT se.student, se.student_name, sec.course_status as status, sec.course_name as enrolled_course
		FROM `tabProgram Enrollment` sec 
		JOIN `tabStudent Enrollment` se ON se.name = sec.parent 
		WHERE 1=1 {course_condition}
	""", tuple(args_tuple), as_dict=True)
	
	return students

@frappe.whitelist()
def apply_schema_to_courses(exam_plan, schema_doctype, schema_name, courses):
	if isinstance(courses, str):
		courses = json.loads(courses)
	
	schema_field = "exam_schema" if schema_doctype == "Exam Schema" else "grading_schema"
		
	for course_name in courses:
		existing = frappe.db.exists("Exam Course Mapping", {"examination_plan": exam_plan, "course": course_name})
		if existing:
			frappe.db.set_value("Exam Course Mapping", existing, schema_field, schema_name)
		else:
			doc = frappe.get_doc({
				"doctype": "Exam Course Mapping",
				"examination_plan": exam_plan,
				"course": course_name,
				schema_field: schema_name,
				"mapped_unmapped_status": "Mapped"
			})
			doc.flags.ignore_mandatory = True
			doc.insert(ignore_permissions=True)
	frappe.db.commit()

@frappe.whitelist()
def unmap_schema_from_courses(exam_plan, courses):
	if isinstance(courses, str):
		courses = json.loads(courses)
		
	for course_name in courses:
		existing = frappe.db.exists("Exam Course Mapping", {"examination_plan": exam_plan, "course": course_name})
		if existing:
			frappe.delete_doc("Exam Course Mapping", existing, ignore_permissions=True)
	frappe.db.commit()

