frappe.query_reports["Application Trends"] = {
	"filters": [
		{
			"fieldname": "admission_year",
			"label": __("Admission Year"),
			"fieldtype": "Link",
			"options": "Admission Year",
			"default": ""
		},
		{
			"fieldname": "admission_cycle",
			"label": __("Admission Cycle"),
			"fieldtype": "Link",
			"options": "Admission Cycle",
			"get_query": function () {
				let year = frappe.query_report.get_filter_value('admission_year');
				if (year) {
					return {
						filters: { 'admission_year': year }
					};
				}
			}
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
			"fieldname": "group_by",
			"label": __("Group By"),
			"fieldtype": "Select",
			"options": "Day\nWeek\nMonth",
			"default": "Day",
			"reqd": 1
		}
	]
};
