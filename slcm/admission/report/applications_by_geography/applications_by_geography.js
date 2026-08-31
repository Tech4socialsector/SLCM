// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.query_reports["Applications by Geography"] = {
	"filters": [
		{
			"fieldname": "state",
			"label": __("State"),
			"fieldtype": "Link",
			"options": "State",
			"reqd": 0
		},
		{
			"fieldname": "country",
			"label": __("Country"),
			"fieldtype": "Link",
			"options": "Country",
			"reqd": 0
		}
	]
};
