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
			"label": "Changed On",
			"fieldname": "changed_on",
			"fieldtype": "Datetime",
			"width": 160,
		},
		{
			"label": "Exam Plan",
			"fieldname": "exam_plan",
			"fieldtype": "Link",
			"options": "Exam Plan",
			"width": 180,
		},
		{
			"label": "Course",
			"fieldname": "course",
			"fieldtype": "Link",
			"options": "Course",
			"width": 200,
		},
		{
			"label": "Changed By",
			"fieldname": "changed_by",
			"fieldtype": "Link",
			"options": "User",
			"width": 160,
		},
		{
			"label": "Old Evaluation Schema",
			"fieldname": "old_evaluation_schema",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": "New Evaluation Schema",
			"fieldname": "new_evaluation_schema",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": "Old Grade Schema",
			"fieldname": "old_grade_schema",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": "New Grade Schema",
			"fieldname": "new_grade_schema",
			"fieldtype": "Data",
			"width": 160,
		},
	]


def get_data(filters):
	conditions = []
	values = {}

	if filters.get("exam_plan"):
		conditions.append("exam_plan = %(exam_plan)s")
		values["exam_plan"] = filters["exam_plan"]

	if filters.get("course"):
		conditions.append("course = %(course)s")
		values["course"] = filters["course"]

	if filters.get("changed_by"):
		conditions.append("changed_by = %(changed_by)s")
		values["changed_by"] = filters["changed_by"]

	if filters.get("from_date"):
		conditions.append("DATE(changed_on) >= %(from_date)s")
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions.append("DATE(changed_on) <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

	data = frappe.db.sql(
		f"""
		SELECT
			changed_on,
			exam_plan,
			course,
			changed_by,
			old_evaluation_schema,
			new_evaluation_schema,
			old_grade_schema,
			new_grade_schema
		FROM `tabSchema Change Log`
		{where_clause}
		ORDER BY changed_on DESC
		LIMIT 500
		""",
		values,
		as_dict=True,
	)

	return data


def get_filters():
	return [
		{
			"fieldname": "exam_plan",
			"label": "Exam Plan",
			"fieldtype": "Link",
			"options": "Exam Plan",
		},
		{
			"fieldname": "course",
			"label": "Course",
			"fieldtype": "Link",
			"options": "Course",
		},
		{
			"fieldname": "changed_by",
			"label": "Changed By",
			"fieldtype": "Link",
			"options": "User",
		},
		{
			"fieldname": "from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"default": frappe.utils.add_months(frappe.utils.today(), -1),
		},
		{
			"fieldname": "to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": frappe.utils.today(),
		},
	]
