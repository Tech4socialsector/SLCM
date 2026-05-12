frappe.query_reports["Weekly Revenue Trend"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.nowdate(), -3)
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.nowdate()
		},
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
	}
};
