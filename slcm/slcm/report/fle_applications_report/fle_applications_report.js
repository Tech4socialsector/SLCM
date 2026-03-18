frappe.query_reports["FLE Applications Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "payment_status",
			label: __("Payment Status"),
			fieldtype: "Select",
			options: "\nAuthorized\nCaptured\nFailed\nRefunded\nPending\nCancelled\nPayment Initiated",
		},
		{
			fieldname: "enrollment_status",
			label: __("Enrollment Status"),
			fieldtype: "Select",
			options: "\nSave\nEnrolled\nIn Progress\nCompleted\nFailed\nDropped\nCertificate Issued",
		},
		{
			fieldname: "candidate_gender",
			label: __("Gender"),
			fieldtype: "Select",
			options: "\nMale\nFemale\nOther",
		},
		{
			fieldname: "candidate_nationality",
			label: __("Nationality"),
			fieldtype: "Select",
			options: "\nIndian\nForeign National",
		},
		{
			fieldname: "candidates_state",
			label: __("State"),
			fieldtype: "Select",
			options: [
				"",
				"Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
				"Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
				"Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
				"Nagaland", "New Delhi", "Odisha", "Punjab", "Rajasthan", "Sikkim",
				"Tamilnadu", "Telengana", "Tripura", "Uttar Pradesh", "Uttarakhand",
				"West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
				"Dadra and Nagar Haveli and Daman and Diu", "Delhi (NCT)", "Jammu & Kashmir",
				"Ladakh", "Lakshadweep", "Puducherry", "Other"
			].join("\n"),
		},
		{
			fieldname: "year_of_passing",
			label: __("Year of Passing"),
			fieldtype: "Select",
			options: "\n2016\n2017\n2018\n2019\n2020\n2021\n2022\n2023\n2024\n2025\n2026\nPrior to 2016",
		},
		{
			fieldname: "lms_account_created",
			label: __("LMS Account Created"),
			fieldtype: "Select",
			options: "\nYes\nNo",
			on_change: function () {
				// map Yes/No to 1/0 for the backend
				const val = frappe.query_report.get_filter_value("lms_account_created");
				if (val === "Yes") {
					frappe.query_report.set_filter_value("lms_account_created", 1);
				} else if (val === "No") {
					frappe.query_report.set_filter_value("lms_account_created", 0);
				}
			},
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		// Render attached-file columns as clickable links
		const file_cols = ["candidate_photo", "id_card_scan", "signature_scan"];
		if (file_cols.includes(column.fieldname) && value) {
			return `<a href="${value}" target="_blank" rel="noopener noreferrer">${__("View File")}</a>`;
		}
		return default_formatter(value, row, column, data);
	},
};
