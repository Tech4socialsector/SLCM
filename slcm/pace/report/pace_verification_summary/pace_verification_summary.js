// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.query_reports["PACE Verification Summary"] = {
	filters: [
        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date"
        },
        {
            fieldname: "programme",
            label: "Programme",
            fieldtype: "Link",
            options: "Programme"
        },
        {
            fieldname: "assigned_verifier",
            label: "Verifier",
            fieldtype: "Link",
            options: "User"
        }
    ],
};
