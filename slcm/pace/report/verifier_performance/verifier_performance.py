import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	
	total_assigned = sum(d.get("total_assigned", 0) for d in data)
	total_verified = sum(d.get("verified", 0) for d in data)
	efficiency = (total_verified / total_assigned * 100) if total_assigned > 0 else 0
	
	report_summary = [
		{
			"value": efficiency,
			"indicator": "Green",
			"label": _("Team Efficiency"),
			"datatype": "Percent",
		}
	]

	return columns, data, None, chart, report_summary

def get_columns():
	return [
		{
			"label": _("Verifier"),
			"fieldname": "verifier",
			"fieldtype": "Link",
			"options": "User",
			"width": 200
		},
		{
			"label": _("Total Assigned"),
			"fieldname": "total_assigned",
			"fieldtype": "Int",
			"width": 120
		},
		{
			"label": _("Verified"),
			"fieldname": "verified",
			"fieldtype": "Int",
			"width": 120
		},
		{
			"label": _("Pending"),
			"fieldname": "pending",
			"fieldtype": "Int",
			"width": 120
		},
		{
			"label": _("Efficiency %"),
			"fieldname": "efficiency",
			"fieldtype": "Percent",
			"width": 120
		}
	]

def get_data(filters):
	conditions = " AND assigned_verifier IS NOT NULL"
	values = {}

	if filters.get("academic_year"):
		conditions += " AND academic_year = %(academic_year)s"
		values["academic_year"] = filters.get("academic_year")

	data = frappe.db.sql(f"""
		SELECT 
			assigned_verifier as verifier,
			COUNT(name) as total_assigned,
			SUM(CASE WHEN status IN ('Verified', 'Fee Paid', 'Admitted') THEN 1 ELSE 0 END) as verified
		FROM `tabPACE Application`
		WHERE docstatus < 2 {conditions}
		GROUP BY verifier
		ORDER BY total_assigned DESC
	""", values, as_dict=1)

	for d in data:
		d["pending"] = d["total_assigned"] - d["verified"]
		d["efficiency"] = (d["verified"] / d["total_assigned"] * 100) if d["total_assigned"] > 0 else 0

	return data

def get_chart(data):
	if not data:
		return None

	return {
		"data": {
			"labels": [d["verifier"] for d in data],
			"datasets": [
				{
					"name": _("Verified"),
					"values": [d["verified"] for d in data]
				},
				{
					"name": _("Pending"),
					"values": [d["pending"] for d in data]
				}
			]
		},
		"type": "bar",
		"colors": ["#34a853", "#fbbc05"],
		"barOptions": {
			"stacked": 1
		}
	}
