frappe.query_reports["Fee Refund Register"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "student",
			label: __("Student"),
			fieldtype: "Link",
			options: "Student Master",
		},
		{
			fieldname: "refund_type",
			label: __("Refund Type"),
			fieldtype: "Select",
			options: "\nOverpayment\nWithdrawal\nDeposit Refund\nOther",
		},
		{
			fieldname: "refund_mode",
			label: __("Refund Mode"),
			fieldtype: "Select",
			options: "\nCash\nBank Transfer\nCheque\nOnline",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nApproved\nReversed",
		},
	],
};
