import frappe
from frappe import _

def execute(filters=None):
	if not filters:
		filters = {}
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	return columns, data, None, chart

def get_columns():
	return [
		{
			"label": _("Period"),
			"fieldname": "period",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("Application Count"),
			"fieldname": "count",
			"fieldtype": "Int",
			"width": 150
		}
	]

def get_data(filters):
	conditions = ""
	values = {}

	if filters.get("admission_year"):
		conditions += " AND admission_year = %(admission_year)s"
		values["admission_year"] = filters.get("admission_year")

	if filters.get("admission_cycle"):
		conditions += " AND admission_cycle = %(admission_cycle)s"
		values["admission_cycle"] = filters.get("admission_cycle")

	if filters.get("campus"):
		conditions += " AND campus = %(campus)s"
		values["campus"] = filters.get("campus")

	if filters.get("program"):
		conditions += " AND program = %(program)s"
		values["program"] = filters.get("program")

	group_by = filters.get("group_by", "Day")
	
	if group_by == "Day":
		date_format = "DATE_FORMAT(creation, '%%Y-%%m-%%d')"
	elif group_by == "Week":
		date_format = "DATE_FORMAT(creation, '%%Y - Week %%u')"
	else: # Month
		date_format = "DATE_FORMAT(creation, '%%Y-%%m')"

	data = frappe.db.sql(f"""
		SELECT 
			{date_format} as period,
			COUNT(name) as count
		FROM `tabApplicant`
		WHERE docstatus < 2 {conditions}
		GROUP BY period
		ORDER BY MIN(creation)
	""", values, as_dict=1)

	return data

def get_chart(data):
	if not data:
		return None
		
	labels = []
	values = []
	
	for row in data:
		labels.append(row.get("period"))
		values.append(row.get("count"))
		
	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": _("Applications"),
					"values": values
				}
			]
		},
		"type": "line",
		"height": 300,
		"colors": ["#1a73e8"],
		"lineOptions": {
			"regionFill": 1,
			"spline": 1,
			"dotSize": 6
		}
	}
