// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.query_reports["PACE Verifier Performance"] = {
	filters: [
		{
			fieldname: "academic_year",
			label: "Academic Year",
			fieldtype: "Link",
			options: "Academic Year",
			default: frappe.defaults.get_user_default("academic_year")
		},
		{
			fieldname: "programme",
			label: "Programme",
			fieldtype: "Link",
			options: "PACE Programme"
		},
		{
			fieldname: "assigned_verifier",
			label: "Verifier",
			fieldtype: "Link",
			options: "User",
			get_query: () => {
				return {
					filters: {
						"enabled": 1
					}
				};
			}
		},
		{
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date"
		},
		{
			fieldname: "to_date",
			label: "To Date",
			fieldtype: "Date"
		}
	],
	onload: function(report) {
		if (frappe.user_roles.includes("Document Verifier") && !frappe.user_roles.includes("PACE Manager") && !frappe.user_roles.includes("System Manager")) {
			report.set_filter_value("assigned_verifier", frappe.session.user);
			report.get_filter("assigned_verifier").df.hidden = 1;
			report.refresh();
		}
	}
};
