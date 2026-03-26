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
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "total_classes",
			"label": _("Total Classes"),
			"fieldtype": "Float",
			"width": 100
		},
		{
			"fieldname": "raw_attended_classes",
			"label": _("Class Attended"),
			"fieldtype": "Float",
			"width": 100
		},
		{
			"fieldname": "office_hours_attended",
			"label": _("Office Hours Attended"),
			"fieldtype": "Float",
			"width": 100
		},
		{
			"fieldname": "total_hours_attended_calc",
			"label": _("Total Hours (Class+Office)"),
			"fieldtype": "Float",
			"width": 120
		},
		{
			"fieldname": "is_condonation_applied",
			"label": _("Is Condonation Applied"),
			"fieldtype": "Data",
			"width": 100
		},
		{
			"fieldname": "condonation_hours",
			"label": _("Condonation Hours"),
			"fieldtype": "Float",
			"width": 100
		},
		{
			"fieldname": "condonation_reason",
			"label": _("Condonation Reason"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "condonation_proof",
			"label": _("Condonation Proof"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "is_fa_mfa_applied",
			"label": _("Is FA/MFA Applied"),
			"fieldtype": "Data",
			"width": 100
		},
		{
			"fieldname": "fa_mfa_reason",
			"label": _("FA/MFA Reason"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "fa_mfa_proof",
			"label": _("FA/MFA Proof"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "percentage_before_condonation",
			"label": _("% Before Condonation"),
			"fieldtype": "Percent",
			"width": 100
		},
		{
			"fieldname": "percentage_after_condonation",
			"label": _("% After Condonation"),
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
			c.course_name as course,
			att.total_classes,
			
			COALESCE(att.total_attended_class_hours, 0) as raw_attended_classes,
			COALESCE(att.total_office_hours, 0) as office_hours_attended,
			(COALESCE(att.total_attended_class_hours, 0) + COALESCE(att.total_office_hours, 0)) as total_hours_attended_calc,
			
			CASE WHEN (SELECT COUNT(*) FROM `tabAttendance Condonation Reference` WHERE parent=att.name) > 0 THEN 'Yes' ELSE 'No' END as is_condonation_applied,
			(SELECT COALESCE(SUM(number_of_hours), 0) FROM `tabAttendance Condonation Reference` WHERE parent=att.name) as condonation_hours,
			(SELECT GROUP_CONCAT(condonation_reason SEPARATOR ', ') FROM `tabAttendance Condonation Reference` WHERE parent=att.name) as condonation_reason,
			(SELECT GROUP_CONCAT(proof_document SEPARATOR ', ') FROM `tabAttendance Condonation Reference` WHERE parent=att.name) as condonation_proof,
			
			CASE WHEN (SELECT COUNT(*) FROM `tabAttendance FA MFA Reference` WHERE parent=att.name) > 0 THEN 'Yes' ELSE 'No' END as is_fa_mfa_applied,
			(SELECT GROUP_CONCAT(reason SEPARATOR ', ') FROM `tabAttendance FA MFA Reference` WHERE parent=att.name) as fa_mfa_reason,
			(SELECT GROUP_CONCAT(proof_document SEPARATOR ', ') FROM `tabAttendance FA MFA Reference` WHERE parent=att.name) as fa_mfa_proof,
			
			CASE 
				WHEN att.total_class_hours > 0 THEN 
					((COALESCE(att.total_attended_class_hours, 0) + COALESCE(att.total_office_hours, 0)) / att.total_class_hours) * 100 
				ELSE 0 
			END as percentage_before_condonation,
			
			att.attendance_percentage as percentage_after_condonation,
			
			CASE
				WHEN att.eligible_for_exam = 1 THEN 'Eligible'
				ELSE 'Not Eligible'
			END as status
		FROM
			`tabAttendance Summary` att
		LEFT JOIN
			`tabStudent Master` s ON att.student = s.name
		LEFT JOIN
			`tabCourse` c ON att.course = c.name
		WHERE
			att.docstatus < 2
			{conditions}
		ORDER BY
			att.student, c.course_name
	""".format(conditions=conditions)

	results = frappe.db.sql(query, filters, as_dict=True)
	
	return results
