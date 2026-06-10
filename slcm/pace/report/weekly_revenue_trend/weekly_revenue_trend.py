import frappe
from frappe import _
from frappe.utils import formatdate

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	
	total_revenue = sum(d.get("total_revenue", 0) for d in data)
	report_summary = [
		{
			"value": total_revenue,
			"indicator": "Green",
			"label": _("Total Revenue"),
			"datatype": "Currency",
			"currency": frappe.defaults.get_global_default("currency")
		}
	]

	return columns, data, None, chart, report_summary

def get_columns():
	return [
		{
			"label": _("Week"),
			"fieldname": "week_num",
			"fieldtype": "Int",
			"width": 80
		},
		{
			"label": _("Year"),
			"fieldname": "year",
			"fieldtype": "Data",
			"width": 80
		},
		{
			"label": _("Week Start"),
			"fieldname": "week_start",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": _("Application Fee"),
			"fieldname": "app_fee_rev",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140
		},
		{
			"label": _("Admission Fee"),
			"fieldname": "adm_fee_rev",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140
		},
		{
			"label": _("Total Revenue"),
			"fieldname": "total_revenue",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 150
		}
	]

def get_data(filters):
	conditions = ""
	values = {}

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND DATE(payment_date) BETWEEN %(from_date)s AND %(to_date)s"
		values["from_date"] = filters.get("from_date")
		values["to_date"] = filters.get("to_date")

	if filters.get("academic_year"):
		conditions += " AND academic_year = %(academic_year)s"
		values["academic_year"] = filters.get("academic_year")

	if filters.get("programme"):
		conditions += " AND program = %(programme)s"
		values["programme"] = filters.get("programme")

	# SQL to group by week and pivot by fee_type
	raw_data = frappe.db.sql(f"""
		SELECT 
			WEEK(payment_date) as week_num,
			YEAR(payment_date) as year,
			MIN(DATE(payment_date)) as week_start,
			SUM(CASE WHEN fee_type = 'Application Fee' THEN amount ELSE 0 END) as app_fee_rev,
			SUM(CASE WHEN fee_type = 'Admission Fee' THEN amount ELSE 0 END) as adm_fee_rev,
			SUM(amount) as total_revenue
		FROM `tabPACE Receipt`
		WHERE docstatus < 2 {conditions}
		GROUP BY year, week_num
		ORDER BY year ASC, week_num ASC
	""", values, as_dict=1)

	return raw_data

def get_chart(data):
	if not data:
		return None

	labels = []
	app_values = []
	adm_values = []
	total_values = []
	
	for d in data:
		labels.append(f"W{d['week_num']} ({formatdate(d['week_start'], 'MMM dd')})")
		app_values.append(d['app_fee_rev'])
		adm_values.append(d['adm_fee_rev'])
		total_values.append(d['total_revenue'])

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": _("Application Fee"),
					"values": app_values
				},
				{
					"name": _("Admission Fee"),
					"values": adm_values
				},
				{
					"name": _("Total Revenue"),
					"values": total_values
				}
			]
		},
		"type": "bar",
		"colors": ["#7c3aed", "#db2777", "#2563eb"]
	}
