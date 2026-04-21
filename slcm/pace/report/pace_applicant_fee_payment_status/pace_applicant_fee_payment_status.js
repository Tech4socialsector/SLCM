// Copyright (c) 2026, Tech4socialsector and contributors
// For license information, please see license.txt

frappe.query_reports["PACE Applicant Fee Payment Status"] = {
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
			"options": "\nAdmission Fee\nApplication Fee"
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
			"options": "\nDraft\nAssigned\nPartially Paid\nPaid\nCancelled\nConverted\nWithdrawn\nEnrolled"
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
		}
	],
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "status") {
			if (value == __("Paid") || value == __("Enrolled")) {
				value = `<span style="color:green; font-weight:bold;">${value}</span>`;
			} else if (value == __("Partially Paid")) {
				value = `<span style="color:orange; font-weight:bold;">${value}</span>`;
			} else if (value == __("Cancelled")) {
				value = `<span style="color:red; font-weight:bold;">${value}</span>`;
			}
		}

		return value;
	}
};
