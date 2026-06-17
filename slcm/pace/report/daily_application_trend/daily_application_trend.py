import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	
	# Calculate total for the summary row
	total_count = sum(d.get("count", 0) for d in data)
	report_summary = [
		{
			"value": total_count,
			"indicator": "Blue",
			"label": _("Total Completed Applications"),
			"datatype": "Int",
		}
	]

	return columns, data, None, chart, report_summary

def get_columns():
	return [
		{
			"label": _("Date"),
			"fieldname": "date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": _("Completed Applications"),
			"fieldname": "count",
			"fieldtype": "Int",
			"width": 180
		}
	]

def get_data(filters):
	filters = filters or {}
	conditions = ""
	values = {}

	if filters.get("academic_year"):
		conditions += " AND academic_year = %(academic_year)s"
		values["academic_year"] = filters.get("academic_year")

	if filters.get("programme"):
		conditions += " AND programme = %(programme)s"
		values["programme"] = filters.get("programme")

	# If a specific status is filtered, use it, otherwise default to 'Completed'
	if filters.get("status"):
		conditions += " AND status = %(status)s"
		values["status"] = filters.get("status")
	else:
		conditions += " AND status = 'Completed'"

	if filters.get("gender"):
		conditions += " AND gender = %(gender)s"
		values["gender"] = filters.get("gender")

	if filters.get("category"):
		conditions += " AND category = %(category)s"
		values["category"] = filters.get("category")

	data = frappe.db.sql(f"""
		SELECT 
			DATE(submission_date) as date,
			COUNT(name) as count
		FROM `tabPACE Application`
		WHERE docstatus < 2 {conditions} AND submission_date IS NOT NULL
		GROUP BY DATE(submission_date)
		ORDER BY DATE(submission_date) ASC
	""", values, as_dict=1)

	return data

def get_chart(data):
	if not data:
		return None

	return {
		"data": {
			"labels": [d["date"] for d in data],
			"datasets": [
				{
					"name": _("Completed Applications"),
					"values": [d["count"] for d in data]
				}
			]
		},
		"type": "line",
		"colors": ["#1a73e8"],
		"lineOptions": {
			"regionFill": 1,
			"spline": 1
		}
	}
