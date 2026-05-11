frappe.query_reports["Verifier Performance"] = {
	"filters": [
		{
			"fieldname": "academic_year",
			"label": __("Academic Year"),
			"fieldtype": "Link",
			"options": "Academic Year"
		}
	],
	"onload": function (report) {
		report.page.add_inner_button(__("Refresh"), function () {
			report.refresh();
		});
		report.chart_options = { height: 300 };
		report.refresh();
	}
};
