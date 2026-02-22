# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	report_summary = get_report_summary(data)
	return columns, data, None, chart, report_summary

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
	data = frappe.db.get_all("Applicant Fee Assignment",
		fields=["status", "count(name) as count", "sum(total_amount) as total_amount"],
		group_by="status"
	)
	return data

def get_chart(data):
	labels = [d.status for d in data]
	values = [d.count for d in data]
	
	return {
		"data": {
			"labels": labels,
			"datasets": [{"values": values}]
		},
		"type": "donut",
		"height": 250
	}

def get_report_summary(data):
	total_assigned = 0
	converted_count = 0
	total_count = 0
	pending_amount = 0
	
	for d in data:
		total_count += d.count
		total_assigned += d.total_amount
		if d.status == "Converted":
			converted_count += d.count
		if d.status in ["Assigned", "Partially Paid"]:
			pending_amount += d.total_amount
	
	conversion_rate = (converted_count / total_count * 100) if total_count > 0 else 0
	
	return [
		{
			"value": pending_amount,
			"indicator": "Red" if pending_amount > 0 else "Green",
			"label": _("Total Pending Collection"),
			"datatype": "Currency"
		},
		{
			"value": conversion_rate,
			"indicator": "Blue",
			"label": _("Conversion Rate"),
			"datatype": "Percent"
		}
	]
