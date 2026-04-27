// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.query_reports["PACE Verification Summary"] = {
	filters: [
		{
			fieldname: "academic_year",
			label: "Academic Year",
			fieldtype: "Link",
			options: "Academic Year",
			default: frappe.defaults.get_user_default("academic_year"),
			reqd: 1
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
			fieldtype: (frappe.user_roles.includes("Document Verifier") && 
						!frappe.user_roles.includes("PACE Manager") && 
						!frappe.user_roles.includes("System Manager") &&
						!frappe.user_roles.includes("Admission Admin") &&
						!frappe.user_roles.includes("PACE Admission Manager")) ? "Data" : "Link",
			options: "User",
			get_query: () => {
				return { filters: { "enabled": 1 } };
			}
		}
	],
	onload: function(report) {
		if (frappe.user_roles.includes("Document Verifier") && 
			!frappe.user_roles.includes("PACE Manager") && 
			!frappe.user_roles.includes("System Manager") &&
			!frappe.user_roles.includes("Admission Admin") &&
			!frappe.user_roles.includes("PACE Admission Manager")) {
			
			report.set_filter_value("assigned_verifier", frappe.session.user);
			const filter = report.get_filter("assigned_verifier");
			if (filter) {
				filter.df.hidden = 1;
				filter.df.read_only = 1;
			}
			report.refresh();
		}
	}
};
