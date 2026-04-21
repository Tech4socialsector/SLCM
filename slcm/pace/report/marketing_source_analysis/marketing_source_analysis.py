import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	
	total_paid = sum(d.get("paid_apps", 0) for d in data)
	report_summary = [
		{
			"value": total_paid,
			"indicator": "Green",
			"label": _("Total Paid Applications"),
			"datatype": "Int",
		}
	]

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
			COALESCE(how_did_you_hear_about_us, 'Not Specified') as source,
			COUNT(name) as total_apps,
			SUM(CASE WHEN status IN ('Fee Paid', 'Admitted') THEN 1 ELSE 0 END) as paid_apps
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

	return {
		"data": {
			"labels": [d["source"] for d in data],
			"datasets": [
				{
					"name": _("Paid Applications"),
					"values": [d["paid_apps"] for d in data]
				}
			]
		},
		"type": "donut",
		"colors": ["#4285F4", "#FBBC05", "#34A853", "#EA4335", "#673AB7", "#E91E63", "#009688", "#795548", "#607D8B", "#FF5722"]
	}
