frappe.query_reports["Overall Merit Report"] = {
	"filters": [
		{
			"fieldname": "admission_cycle",
			"label": __("Admission Cycle"),
			"fieldtype": "Link",
			"options": "Admission Cycle",
			"reqd": 1
		},
		{
			"fieldname": "campus",
			"label": __("Campus"),
			"fieldtype": "Link",
			"options": "Campus",
			"reqd": 1
		},
		{
			"fieldname": "program",
			"label": __("Programme"),
			"fieldtype": "Link",
			"options": "Programme"
		},
		{
			"fieldname": "merit_processing_stage",
			"label": __("Stage"),
			"fieldtype": "Select",
			"options": "\nShortlisting Rank List\nFinal Allotment Ranking",
			"default": "Final Allotment Ranking"
		}
	],
	"onload": function(report) {
		report.page.add_inner_button(__("Refresh"), function() {
			report.refresh();
		});
	}
};
