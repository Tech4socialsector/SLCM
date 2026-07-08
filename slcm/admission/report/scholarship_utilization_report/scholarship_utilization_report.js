// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.query_reports["Scholarship Utilization Report"] = {
	"filters": [
		{
			"fieldname": "admission_cycle",
			"label": __("Admission Cycle"),
			"fieldtype": "Link",
			"options": "Admission Cycle"
		},
		{
			"fieldname": "campus",
			"label": __("Campus"),
			"fieldtype": "Link",
			"options": "Campus"
		},
		{
			"fieldname": "program",
			"label": __("Programme"),
			"fieldtype": "Link",
			"options": "Programme"
		},
		{
			"fieldname": "scholarship_scheme",
			"label": __("Scholarship Scheme"),
			"fieldtype": "Link",
			"options": "Scholarship Scheme"
		}
	]
};
