# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	columns = [
		{
			"fieldname": "student",
			"label": _("Student"),
			"fieldtype": "Link",
			"options": "Student Master",
			"width": 150
		},
		{
			"fieldname": "student_name",
			"label": _("Student Name"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "program",
			"label": _("Program"),
			"fieldtype": "Link",
			"options": "Cohort",
			"width": 120
		},
		{
			"fieldname": "section",
			"label": _("Section"),
			"fieldtype": "Link",
			"options": "Program Batch Section",
			"width": 100
		},
		{
			"fieldname": "course",
			"label": _("Course"),
			"fieldtype": "Link",
			"options": "Course",
			"width": 200
		},
		{
			"fieldname": "total_classes",
			"label": _("Total Classes"),
			"fieldtype": "Int",
			"width": 100
		},
		{
			"fieldname": "attended_classes",
			"label": _("Attended Classes"),
			"fieldtype": "Int",
			"width": 100
		},
		{
			"fieldname": "attendance_percentage",
			"label": _("Percentage"),
			"fieldtype": "Percent",
			"width": 100
		},
		{
			"fieldname": "status",
			"label": _("Status"),
			"fieldtype": "Data",
			"width": 100
		}
	]
	return columns

def get_data(filters):
	data = []
	
	conditions = ""
	if filters.get("department"):
		conditions += " AND s.department = %(department)s"
	if filters.get("program"):
		conditions += " AND s.programme = %(program)s"
	if filters.get("section"):
		conditions += " AND att.section = %(section)s" # Fetch section from Attendance Summary
	if filters.get("course"):
		conditions += " AND att.course = %(course)s"

	# Fetch data from Attendance Summary
	query = """
		SELECT
			att.student,
			att.student_name,
			s.programme as program,
			att.section as section,
			att.course,
			att.total_classes,
			att.attended_classes,
			att.attendance_percentage,
			CASE
				WHEN att.eligible_for_exam = 1 THEN 'Eligible'
				ELSE 'Not Eligible'
			END as status
		FROM
			`tabAttendance Summary` att
		LEFT JOIN
			`tabStudent Master` s ON att.student = s.name
		WHERE
			att.docstatus < 2
			{conditions}
		ORDER BY
			att.student, att.course
	""".format(conditions=conditions)

	results = frappe.db.sql(query, filters, as_dict=True)
	
	return results
