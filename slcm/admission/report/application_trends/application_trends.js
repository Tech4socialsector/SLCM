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
	],
	"onload": function (report) {
		report.page.add_inner_button(__("Refresh"), function () {
			report.refresh();
		});
		// Force standard chart height
		report.chart_options = { height: 300 };
		report.refresh();
	},
	"get_chart_data": function (columns, result) {
		if (!result || result.length === 0) return null;

		return {
			data: {
				labels: result.map(d => d.period),
				datasets: [{
					name: __("Applications"),
					values: result.map(d => d.count)
				}]
			},
			type: 'line',
			height: 300,
			colors: ['#1a73e8'],
			lineOptions: {
				regionFill: 1,
				spline: 1,
				dotSize: 6     // Makes single points much more visible
			}
		};
	}
};
