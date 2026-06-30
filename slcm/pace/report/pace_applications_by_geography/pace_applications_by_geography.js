// Copyright (c) 2026
// For license information, please see license.txt

frappe.query_reports["PACE Applications by Geography"] = {
	filters: [
		{
			fieldname: "country",
			label: __("Country"),
			fieldtype: "Link",
			options: "Country",
			default: "India",
			reqd: 0,
		},
		{
			fieldname: "state",
			label: __("State"),
			fieldtype: "Link",
			options: "State",
			reqd: 0,
			get_query: function () {
				const country = frappe.query_report.get_filter_value("country");
				if (!country) {
					return {};
				}
				return {
					filters: {
						country: country,
					},
				};
			},
		},
		{
			fieldname: "district",
			label: __("City"),
			fieldtype: "Link",
			options: "City",
			default: "",
			reqd: 0,
			get_query: function () {
				const country = frappe.query_report.get_filter_value("country");
				const state = frappe.query_report.get_filter_value("state");

				let filters = {};
				if (country) filters.country = country;
				if (state) filters.state = state;

				return { filters: filters };
			},
		},
	],
};