// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.query_reports["Applicant Fee Payments"] = {
    "filters": [
        {
            "fieldname": "admission_year",
            "label": __("Admission Year"),
            "fieldtype": "Link",
            "options": "Admission Year",
            "default": ""
        },
        {
            "fieldname": "campus",
            "label": __("Campus"),
            "fieldtype": "Link",
            "options": "Campus"
        },
        {
            "fieldname": "program",
            "label": __("Programme"),
            "fieldtype": "Link",
            "options": "Programme"
        },
        {
            "fieldname": "payment_mode",
            "label": __("Payment Mode"),
            "fieldtype": "Select",
            "options": "\nOnline\nCash\nCheque\nNeft/Rtgs"
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        }
    ],
    "onload": function (report) {
        report.page.add_inner_button(__("Refresh"), function () {
            report.refresh();
        });
        report.chart_options = { height: 300 };
        report.refresh();
    },
    "get_chart_data": function (columns, result) {
        if (!result || result.length === 0) return null;

        let mode_counts = {};
        result.forEach(d => {
            let mode = d.payment_mode || __("Not Specified");
            mode_counts[mode] = (mode_counts[mode] || 0) + 1;
        });

        let labels = Object.keys(mode_counts);
        let values = Object.values(mode_counts);

        return {
            data: {
                labels: labels,
                datasets: [{
                    name: __("Transactions"),
                    values: values
                }]
            },
            type: 'donut',
            height: 300,
            colors: ['#42a5f5', '#66bb6a', '#ffa726', '#ef5350', '#ab47bc', '#8d6e63', '#78909c']
        };
    },
    "get_report_summary": function (columns, result) {
        if (!result || result.length === 0) return [];

        let total_amount = 0;
        result.forEach(d => {
            total_amount += flt(d.total_amount);
        });

        return [
            {
                value: result.length,
                indicator: "Blue",
                label: __("Total Transactions"),
                datatype: "Int",
            },
            {
                value: total_amount,
                indicator: "Green",
                label: __("Total Amount Paid"),
                datatype: "Currency",
            }
        ];
    }
};
