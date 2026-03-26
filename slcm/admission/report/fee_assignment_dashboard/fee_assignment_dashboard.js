frappe.query_reports["Fee Assignment Dashboard"] = {
    "filters": [
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
        },
        {
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nAssigned\nPartially Paid\nPaid\nCancelled\nWaived\nConverted"
        }
    ],
    "onload": function (report) {
        report.page.add_inner_button(__("Refresh"), function () {
            report.refresh();
        });
        report.refresh();
    },
    "get_chart_data": function (columns, result) {
        if (!result || result.length === 0) return null;

        return {
            data: {
                labels: result.map(d => d.status),
                datasets: [{
                    values: result.map(d => d.count)
                }]
            },
            type: 'donut',
            height: 250
        };
    },
    "get_report_summary": function (columns, result) {
        if (!result || result.length === 0) return [];

        let total_assigned = 0;
        let converted_count = 0;
        let total_count = 0;
        let pending_amount = 0;

        result.forEach(d => {
            total_count += (d.count || 0);
            total_assigned += (d.total_amount || 0);
            if (d.status === "Converted") converted_count += (d.count || 0);
            if (["Assigned", "Partially Paid"].includes(d.status)) {
                pending_amount += (d.total_amount || 0);
            }
        });

        let conversion_rate = total_count > 0 ? (converted_count / total_count * 100) : 0;

        return [
            {
                value: pending_amount,
                indicator: pending_amount > 0 ? "Red" : "Green",
                label: __("Total Pending Collection"),
                datatype: "Currency"
            },
            {
                value: conversion_rate,
                indicator: "Blue",
                label: __("Conversion Rate"),
                datatype: "Percent"
            }
        ];
    }
};
