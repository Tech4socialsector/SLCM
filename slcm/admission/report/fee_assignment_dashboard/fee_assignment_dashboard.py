# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	
	# Return full tuple to ensure standard 'result' property is populated in JS
	# columns, result, message, chart, report_summary
	return columns, data, None, None, None

def get_columns():
	return [
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Count"),
			"fieldname": "count",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": _("Total Assigned Amount"),
			"fieldname": "total_amount",
			"fieldtype": "Currency",
			"width": 150
		}
	]

def get_data(filters):
	conditions = ""
	values = {}
	
	if filters:
		if filters.get("from_date"):
			conditions += " AND assignment_date >= %(from_date)s"
			values["from_date"] = filters.get("from_date")
		if filters.get("to_date"):
			conditions += " AND assignment_date <= %(to_date)s"
			values["to_date"] = filters.get("to_date")
		if filters.get("status"):
			conditions += " AND status = %(status)s"
			values["status"] = filters.get("status")

	data = frappe.db.sql(f"""
		SELECT 
			status, 
			COUNT(name) as count, 
			SUM(total_amount) as total_amount
		FROM `tabApplicant Fee Assignment`
		WHERE docstatus < 2 {conditions}
		GROUP BY status
	""", values, as_dict=1)
	
	return data

