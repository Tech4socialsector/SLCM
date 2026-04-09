# Copyright (c) 2026, CU and contributors
# For license information, please see license.txt

import frappe
import json


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
def get_exam_components():
	"""Return all active exam components."""
	return frappe.get_all(
		"Exam Component",
		filters={"is_active": 1},
		fields=["name", "component_name", "component_type"],
		order_by="component_name asc",
	)


@frappe.whitelist()
def get_publish_setting(exam_plan):
	"""Return the publish setting for the given exam plan, or None if not found."""
	if not exam_plan:
		return None

	name = frappe.db.get_value(
		"Publish Result Setting", {"exam_plan": exam_plan}, "name"
	)
	if not name:
		return None

	doc = frappe.get_doc("Publish Result Setting", name)
	return {
		"name": doc.name,
		"exam_plan": doc.exam_plan,
		"show_total_marks": doc.show_total_marks,
		"show_sgpa": doc.show_sgpa,
		"hide_sgpa_for_failed": doc.hide_sgpa_for_failed,
		"show_egradesheet": doc.show_egradesheet,
		"no_publish_unpaid": doc.no_publish_unpaid,
		"no_publish_no_feedback": doc.no_publish_no_feedback,
		"components": [
			{
				"component": row.component,
				"component_name": row.component_name,
			}
			for row in doc.publish_components
		],
	}


@frappe.whitelist()
def save_publish_setting(exam_plan, components, show_total_marks, show_sgpa,
                         hide_sgpa_for_failed, show_egradesheet,
                         no_publish_unpaid, no_publish_no_feedback):
	"""Save or create the Publish Result Setting for the given exam plan."""
	if not exam_plan:
		frappe.throw("Exam Plan is required")

	if isinstance(components, str):
		components = json.loads(components)

	def to_int(v):
		return 1 if v in (1, "1", True, "true") else 0

	name = frappe.db.get_value(
		"Publish Result Setting", {"exam_plan": exam_plan}, "name"
	)

	if name:
		doc = frappe.get_doc("Publish Result Setting", name)
	else:
		doc = frappe.new_doc("Publish Result Setting")
		doc.exam_plan = exam_plan

	doc.show_total_marks       = to_int(show_total_marks)
	doc.show_sgpa              = to_int(show_sgpa)
	doc.hide_sgpa_for_failed   = to_int(hide_sgpa_for_failed)
	doc.show_egradesheet       = to_int(show_egradesheet)
	doc.no_publish_unpaid      = to_int(no_publish_unpaid)
	doc.no_publish_no_feedback = to_int(no_publish_no_feedback)

	doc.set("publish_components", [])
	for comp in components:
		doc.append("publish_components", {"component": comp["component"]})

	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"success": True, "name": doc.name}
