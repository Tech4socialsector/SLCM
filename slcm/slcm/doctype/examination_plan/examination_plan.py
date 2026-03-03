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
		mapped = frappe.db.get_value("Examination Plan Course", {"examination_plan": exam_plan_name, "course": course.name}, ["name", "exam_schema"], as_dict=True)
		if mapped:
			course["mapped_id"] = mapped.name
			course["exam_schema"] = mapped.exam_schema
		else:
			course["mapped_id"] = None
			course["exam_schema"] = None

		# Count enrolled students
		enrolled = frappe.db.sql("""
			SELECT COUNT(sec.name) 
			FROM `tabStudent Enrollment Course` sec 
			JOIN `tabStudent Enrollment` se ON se.name = sec.parent 
			WHERE sec.course = %s AND se.term_name = %s
		""", (course.name, plan.academic_term))
		course["enrolled_students"] = enrolled[0][0] if enrolled else 0
			
	return courses

@frappe.whitelist()
def get_course_students(exam_plan_name, course_name):
	plan = frappe.get_doc("Examination Plan", exam_plan_name)
	
	students = frappe.db.sql("""
		SELECT se.student, se.student_name, sec.status 
		FROM `tabStudent Enrollment Course` sec 
		JOIN `tabStudent Enrollment` se ON se.name = sec.parent 
		WHERE sec.course = %s AND se.term_name = %s
	""", (course_name, plan.academic_term), as_dict=True)
	
	return students

@frappe.whitelist()
def apply_schema_to_courses(exam_plan, schema_name, courses):
	if isinstance(courses, str):
		courses = json.loads(courses)
		
	for course_name in courses:
		existing = frappe.db.exists("Examination Plan Course", {"examination_plan": exam_plan, "course": course_name})
		if existing:
			frappe.db.set_value("Examination Plan Course", existing, "exam_schema", schema_name)
		else:
			doc = frappe.get_doc({
				"doctype": "Examination Plan Course",
				"examination_plan": exam_plan,
				"course": course_name,
				"exam_schema": schema_name
			})
			doc.insert(ignore_permissions=True)
	frappe.db.commit()

@frappe.whitelist()
def unmap_schema_from_courses(exam_plan, courses):
	if isinstance(courses, str):
		courses = json.loads(courses)
		
	for course_name in courses:
		existing = frappe.db.exists("Examination Plan Course", {"examination_plan": exam_plan, "course": course_name})
		if existing:
			frappe.delete_doc("Examination Plan Course", existing, ignore_permissions=True)
	frappe.db.commit()

