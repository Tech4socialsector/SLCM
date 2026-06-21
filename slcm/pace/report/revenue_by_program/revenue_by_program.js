frappe.query_reports["Revenue by Program"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.month_start()
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
			"fieldname": "fee_type",
			"label": __("Fee Type"),
			"fieldtype": "Select",
			"options": "\nApplication Fee\nCourse Fee"
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
