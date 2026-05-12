frappe.query_reports["FLE Payment Journal"] = {
	onload: function (report) {
		report.page.add_inner_button(__("Download Excel"), function () {
			frappe.query_report.export_report("Excel");
		}, __("Export"));

		report.page.add_inner_button(__("Download CSV"), function () {
			frappe.query_report.export_report("CSV");
		}, __("Export"));
	},

	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
		},
		{
			fieldname: "payment_status",
			label: __("Payment Status"),
			fieldtype: "Select",
			options: "\nAuthorized\nCaptured\nFailed\nRefunded\nPending\nCancelled\nPayment Initiated",
			default: "Captured",
		},
		// ── Journal metadata (user fills in for accounting export) ──────────
		{
			fieldname: "journal_number_prefix",
			label: __("Journal Number Prefix"),
			fieldtype: "Data",
		},
		{
			fieldname: "journal_number_suffix",
			label: __("Journal Number Suffix"),
			fieldtype: "Data",
		},
		{
			fieldname: "journal_type",
			label: __("Journal Type"),
			fieldtype: "Data",
		},
		{
			fieldname: "currency",
			label: __("Currency"),
			fieldtype: "Data",
			default: "INR",
		},
		{
			fieldname: "account_code",
			label: __("Account Code"),
			fieldtype: "Data",
		},
		{
			fieldname: "account",
			label: __("Account"),
			fieldtype: "Data",
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Data",
		},
		{
			fieldname: "course",
			label: __("Course"),
			fieldtype: "Data",
			default: "Foundations for a Legal Education",
		},
	],
};
