frappe.query_reports["Application Conversion Funnel"] = {
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
		report.chart_options = { height: 300 };
		report.refresh();
	},
	"get_chart_data": function (columns, result) {
		if (!result || result.length === 0) return null;

		return {
			data: {
				labels: result.map(d => d.status === "Under Verification" ? "Under Review" : d.status),
				datasets: [{
					name: __("Applicants"),
					values: result.map(d => d.count)
				}]
			},
			type: 'bar',
			height: 300,
			colors: ["#7cd6fd"],
			barOptions: {
				horizontal: 0
			}
		};
	}
};
