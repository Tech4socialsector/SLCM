frappe.query_reports["Applicant Fee Payment Status"] = {
    filters: [
        {
            "fieldname": "admission_year",
            "label": __("Admission Year"),
            "fieldtype": "Link",
            "options": "Admission Year",
            "default": frappe.defaults.get_user_default("admission_year")
        },
        {
            "fieldname": "fee_type",
            "label": __("Fee Type"),
            "fieldtype": "Select",
            "options": "\nApplication Fee\nConfirmation Fee\nAdmission Fee",
            "default": ""
        },
        {
            "fieldname": "program",
            "label": __("Programme"),
            "fieldtype": "Link",
            "options": "Programme"
        },
        {
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nPaid\nPartially Paid\nPending"
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
            "fieldname": "applicant",
            "label": __("Applicant"),
            "fieldtype": "Link",
            "options": "Applicant"
        },
        {
            "fieldname": "fee_component",
            "label": __("Fee Component"),
            "fieldtype": "Link",
            "options": "Fee Component"
        }
    ],
    "formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "status" && data && data.status) {
            if (data.status === "Paid") {
                return `<span style="color: green; font-weight: bold;">${value}</span>`;
            } else if (data.status === "Pending") {
                return `<span style="color: #ffc107; font-weight: bold;">${value}</span>`; // Yellow/Amber
            } else if (data.status === "Partially Paid") {
                return `<span style="color: blue; font-weight: bold;">${value}</span>`;
            }
        }
        return value;
    },
    "onload": function (report) {
        report.page.add_inner_button(__("Refresh"), function () {
            report.refresh();
        });
        report.chart_options = { height: 300 };
        report.refresh();
    }
};
