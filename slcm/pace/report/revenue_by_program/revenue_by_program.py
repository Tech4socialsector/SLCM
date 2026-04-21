import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	
	total_revenue = sum(d.get("revenue", 0) for d in data)
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
			"label": _("Programme"),
			"fieldname": "program",
			"fieldtype": "Link",
			"options": "PACE Programme",
			"width": 250
		},
		{
			"label": _("Receipt Count"),
			"fieldname": "count",
			"fieldtype": "Int",
			"width": 120
		},
		{
			"label": _("Total Revenue"),
			"fieldname": "revenue",
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

	if filters.get("fee_type"):
		conditions += " AND fee_type = %(fee_type)s"
		values["fee_type"] = filters.get("fee_type")

	data = frappe.db.sql(f"""
		SELECT 
			program,
			COUNT(name) as count,
			SUM(amount) as revenue
		FROM `tabPACE Receipt`
		WHERE docstatus < 2 {conditions}
		GROUP BY program
		ORDER BY revenue DESC
	""", values, as_dict=1)

	return data

def get_chart(data):
	if not data:
		return None

	return {
		"data": {
			"labels": [d["program"] for d in data],
			"datasets": [
				{
					"name": _("Revenue"),
					"values": [d["revenue"] for d in data]
				}
			]
		},
		"type": "bar",
		"colors": ["#34a853"]
	}
