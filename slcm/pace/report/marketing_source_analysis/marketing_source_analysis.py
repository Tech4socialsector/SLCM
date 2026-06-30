import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	
	total_paid = sum(d.get("paid_apps", 0) for d in data)
	report_summary = []

	return columns, data, None, chart, report_summary

def get_columns():
	return [
		{
			"label": _("Marketing Source"),
			"fieldname": "source",
			"fieldtype": "Data",
			"width": 250
		},
		{
			"label": _("Total Applications"),
			"fieldname": "total_apps",
			"fieldtype": "Int",
			"width": 150
		},
		{
			"label": _("Paid Applications"),
			"fieldname": "paid_apps",
			"fieldtype": "Int",
			"width": 150
		},
		{
			"label": _("Conversion %"),
			"fieldname": "conversion_rate",
			"fieldtype": "Percent",
			"width": 120
		}
	]

def get_data(filters):
	conditions = ""
	values = {}

	if filters.get("academic_year"):
		conditions += " AND academic_year = %(academic_year)s"
		values["academic_year"] = filters.get("academic_year")

	if filters.get("programme"):
		conditions += " AND programme = %(programme)s"
		values["programme"] = filters.get("programme")

	data = frappe.db.sql(f"""
		SELECT 
			CASE 
				WHEN how_did_you_hear_about_us IS NULL OR how_did_you_hear_about_us = '' THEN 'Not Specified'
				ELSE how_did_you_hear_about_us 
			END as source,
			COUNT(name) as total_apps,
			SUM(CASE WHEN status IN ('Fee Paid', 'Admitted', 'Enrolled') THEN 1 ELSE 0 END) as paid_apps
		FROM `tabPACE Application`
		WHERE docstatus < 2 {conditions}
		GROUP BY source
		ORDER BY total_apps DESC
	""", values, as_dict=1)

	for d in data:
		d["conversion_rate"] = (d["paid_apps"] / d["total_apps"] * 100) if d["total_apps"] > 0 else 0

	return data

def get_chart(data):
	if not data:
		return None

	# Truncate long marketing source labels to prevent legend overlapping on dashboard/report charts
	labels = []
	for d in data:
		source = d.get("source") or ""
		if len(source) > 15:
			labels.append(source[:15] + "...")
		else:
			labels.append(source)

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": _("Total Applications"),
					"values": [d["total_apps"] for d in data]
				}
			]
		},
		"type": "bar",
		"colors": ["#4285F4", "#FBBC05", "#34A853", "#EA4335", "#673AB7", "#E91E63", "#009688", "#795548", "#607D8B", "#FF5722"]
	}
