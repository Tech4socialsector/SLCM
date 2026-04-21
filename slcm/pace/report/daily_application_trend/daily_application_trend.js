frappe.query_reports["Daily Application Trend"] = {
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
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Link",
			"options": "PACE Application Status"
		},
		{
			"fieldname": "gender",
			"label": __("Gender"),
			"fieldtype": "Select",
			"options": "\nMale\nFemale\nOthers"
		},
		{
			"fieldname": "category",
			"label": __("Category"),
			"fieldtype": "Select",
			"options": "\nGeneral\nSC\nST\nOBC"
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
