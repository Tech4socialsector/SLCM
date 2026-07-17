# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	return columns, data, None, chart

def get_columns():
	return [
		{
			"fieldname": "status",
			"label": _("Analysis"),
			"fieldtype": "Data",
			"width": 300
		},
		{
			"fieldname": "count",
			"label": _("Count"),
			"fieldtype": "Int",
			"width": 150
		}
	]

def get_data(filters):
	conditions = get_conditions(filters)
	
	query = f"""
		SELECT
			status,
			COUNT(name) as count
		FROM
			`tabPACE Application`
		WHERE
			status IN ('Submitted', 'Completed', 'Enrolled')
			{conditions}
		GROUP BY
			status
	"""
	
	results = frappe.db.sql(query, filters, as_dict=1)
	
	counts = {
		"Submitted": 0,
		"Completed": 0,
		"Enrolled": 0
	}
	
	for r in results:
		counts[r.status] = r.count
		
	data = [
		{"status": "Number of applications submitted", "count": counts["Submitted"], "_color": "#BA5A5A"},
		{"status": "Number of application fees paid", "count": counts["Completed"], "_color": "#723EC3"},
		{"status": "Number of applicants enrolled", "count": counts["Enrolled"], "_color": "#9FA1FF"}
	]
	
	return data

def get_conditions(filters):
	conditions = ""
	if not filters:
		return conditions
		
	if filters.get("academic_year"):
		conditions += " AND academic_year = %(academic_year)s"
	if filters.get("programme"):
		conditions += " AND programme = %(programme)s"
	if filters.get("from_date"):
		conditions += " AND submission_date >= %(from_date)s"
	if filters.get("to_date"):
		conditions += " AND submission_date <= %(to_date)s"
		
	return conditions

def get_chart(data):
	labels = [r["status"] for r in data]
	values = [r["count"] for r in data]
	
	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": _("Count"),
					"values": values
				}
			]
		},
		"type": "bar",
		"colors": ["#BA5A5A", "#723EC3", "#9FA1FF"]
	}
