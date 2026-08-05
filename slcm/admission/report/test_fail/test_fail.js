// Copyright (c) 2026, TFSS United contributors
// For license information, please see license.txt

frappe.query_reports["Test Fail"] = {
	filters: [
		{
			fieldname: "academic_year",
			label: __("Academic Year"),
			fieldtype: "Link",
			options: "Academic Year"
		},
		{
			fieldname: "admission_cycle",
			label: __("Admission Cycle"),
			fieldtype: "Link",
			options: "Admission Cycle"
		},
		{
			fieldname: "program_level",
			label: __("Programme Level"),
			fieldtype: "Select",
			options: "\nUndergraduate\nPostgraduate\nResearch Course"
		},
		{
			fieldname: "program",
			label: __("Programme"),
			fieldtype: "Link",
			options: "Programme"
		},
		{
			fieldname: "entrance_test_list",
			label: __("Entrance Test List"),
			fieldtype: "Link",
			options: "Entrance Test List"
		},
		{
			fieldname: "entrance_test_provider",
			label: __("Entrance Test Provider"),
			fieldtype: "Link",
			options: "Entrance Test Provider"
		},
		{
			fieldname: "allocation_date",
			label: __("Entrance Test Date"),
			fieldtype: "Date"
		}
	],
	onload: function(report) {
		if (frappe.user_roles.includes("Entrance Test Provider") &&
			!frappe.user_roles.includes("System Manager") &&
			!frappe.user_roles.includes("Entrance Test Admin")) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Entrance Test Provider",
					filters: { user: frappe.session.user },
					fieldname: "name"
				},
				callback: function(r) {
					if (r.message && r.message.name) {
						report.set_filter_value("entrance_test_provider", r.message.name);
						const field = report.get_filter("entrance_test_provider");
						if (field) {
							field.df.read_only = 1;
							field.refresh();
						}
					}
				}
			});
		}
	}
};
