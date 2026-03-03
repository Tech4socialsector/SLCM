# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters: dict | None = None):
	columns = get_columns()
	data = get_data(filters)
	
	# Return full tuple for better Frappe compatibility
	return columns, data, None, None, None

def get_columns() -> list[dict]:
	return [
		{
			"label": _("Campus"),
			"fieldname": "campus",
			"fieldtype": "Link",
			"options": "Campus",
			"width": 200
		},
		{
			"label": _("Applicant Count"),
			"fieldname": "count",
			"fieldtype": "Int",
			"width": 150
		}
	]

def get_data(filters: dict) -> list[dict]:
	conditions = ""
	values = {}
	
	if filters:
		if filters.get("admission_year"):
			conditions += " AND admission_year = %(admission_year)s"
			values["admission_year"] = filters.get("admission_year")
		if filters.get("admission_cycle"):
			conditions += " AND admission_cycle = %(admission_cycle)s"
			values["admission_cycle"] = filters.get("admission_cycle")
		if filters.get("status"):
			conditions += " AND application_status = %(status)s"
			values["status"] = filters.get("status")

		if filters.get("from_date"):
			conditions += " AND DATE(creation) >= %(from_date)s"
			values["from_date"] = filters.get("from_date")
		
		# Standard to_date should not exceed today
		to_date = filters.get("to_date")
		if to_date:
			today = frappe.utils.today()
			if to_date > today:
				to_date = today
			conditions += " AND DATE(creation) <= %(to_date)s"
			values["to_date"] = to_date

	data = frappe.db.sql(f"""
		SELECT 
			COALESCE(campus, 'Not Specified') as campus,
			COUNT(name) as count
		FROM `tabApplicant`
		WHERE docstatus < 2 {conditions}
		GROUP BY campus
		ORDER BY count DESC
	""", values, as_dict=1)
	
	return data
