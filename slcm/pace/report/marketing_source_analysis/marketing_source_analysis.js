frappe.query_reports["Marketing Source Analysis"] = {
	"filters": [
		{
			"fieldname": "academic_year",
			"label": __("Academic Year"),
			"fieldtype": "Link",
			"options": "Academic Year"
		},
		{
			"fieldname": "programme",
			"label": __("Programme"),
			"fieldtype": "Link",
			"options": "PACE Programme"
		}
	],
	"onload": function (report) {
		report.page.add_inner_button(__("Refresh"), function () {
			report.refresh();
		});
		report.chart_options = {
			height: 300,
			truncateLegends: 1
		};
		report.refresh();
	}
};
