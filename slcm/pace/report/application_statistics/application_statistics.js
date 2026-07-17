// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.query_reports["Application Statistics"] = {
	filters: [
		{
			fieldname: "academic_year",
			label: __("Academic Year"),
			fieldtype: "Link",
			options: "Academic Year"
		},
		{
			fieldname: "programme",
			label: __("Programme"),
			fieldtype: "Link",
			options: "PACE Programme"
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date"
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date"
		}
	],
	onload: function(report) {
		report.page.add_inner_button(__("Refresh Chart"), function() {
			report.refresh();
		});
	}
};
