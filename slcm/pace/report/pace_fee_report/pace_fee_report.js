// Copyright (c) 2026, Tech4socialsector and contributors
// For license information, please see license.txt

frappe.query_reports["PACE Fee Report"] = {
	"filters": [
		{
			"fieldname": "program",
			"label": __("Programme"),
			"fieldtype": "Link",
			"options": "PACE Programme"
		},
		{
			"fieldname": "fee_type",
			"label": __("Fee Type"),
			"fieldtype": "Select",
			"options": "\nCourse Fee\nApplication Fee"
		},
		{
			"fieldname": "academic_year",
			"label": __("Academic Year"),
			"fieldtype": "Link",
			"options": "Academic Year"
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": "\nAssigned\nPaid\nPending"
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date"
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date"
		},
		{
			"fieldname": "fee_component",
			"label": __("Fee Component"),
			"fieldtype": "Link",
			"options": "PACE Fee Component List"
		}
	],
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "status") {
			if (value == __("Paid")) {
				value = `<span style="color:green; font-weight:bold;">${value}</span>`;
			} else if (value == __("Pending")) {
				value = `<span style="color:orange; font-weight:bold;">${value}</span>`;
			} else if (value == __("Assigned")) {
				value = `<span style="color:blue; font-weight:bold;">${value}</span>`;
			}
		}

		if (column.fieldname == "pending_amount") {
			if (data && data.pending_amount > 0) {
				value = `<span style="color:red; font-weight:bold;">${value}</span>`;
			} else if (data && data.pending_amount == 0 && data.final_payable_amount > 0) {
				value = `<span style="color:green; font-weight:bold;">${value}</span>`;
			}
		}

		return value;
	},
	"onload": function (report) {
		// Add prominent Export to Excel button
		report.page.add_inner_button(__("Export to Excel"), function () {
			// Get validated visible indexes
			let visible_idx = report.get_validated_visible_indexes() || [];

			const filters = report.get_filter_values(true);
			const applied_filters = report.get_applied_filters(filters);

			// excluding total row index
			const ignore_visible_idx =
				visible_idx.length ===
				report.data.length - ((report.raw_data && report.raw_data.add_total_row) ? 1 : 0);
			visible_idx = ignore_visible_idx ? [] : visible_idx;

			const args = {
				cmd: "frappe.desk.query_report.export_query",
				report_name: report.report_name,
				custom_columns: report.custom_columns?.length ? report.custom_columns : [],
				file_format_type: "Excel",
				filters: filters,
				applied_filters: applied_filters,
				visible_idx: visible_idx,
				ignore_visible_idx: ignore_visible_idx,
				include_indentation: 0,
				include_filters: 0,
				export_in_background: 0,
				include_hidden_columns: 0,
			};

			// Show a premium, beautiful animated progress bar
			frappe.show_progress(__("Exporting to Excel"), 10, 100, __("Preparing report data..."));

			setTimeout(() => {
				frappe.show_progress(__("Exporting to Excel"), 50, 100, __("Generating Excel spreadsheet..."));
			}, 600);

			setTimeout(() => {
				frappe.show_progress(__("Exporting to Excel"), 90, 100, __("Initiating download..."));
			}, 1200);

			setTimeout(() => {
				frappe.show_progress(__("Exporting to Excel"), 100, 100, __("Download Started!"));

				// Trigger standard Frappe file download directly without dialog
				open_url_post(frappe.request.url, args);

				// Hide progress bar shortly after starting the download
				setTimeout(() => {
					frappe.hide_progress();
				}, 1000);
			}, 1800);
		});
	}
};
