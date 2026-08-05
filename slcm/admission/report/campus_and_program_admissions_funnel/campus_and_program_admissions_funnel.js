frappe.query_reports["Campus and Program Admissions Funnel"] = {
    "filters": [
        {
            "fieldname": "admission_cycle",
            "label": __("Admission Cycle"),
            "fieldtype": "Link",
            "options": "Admission Cycle",
            "default": frappe.defaults.get_user_default("admission_cycle")
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
        }
    ],
    "get_chart_data": function (columns, result) {
        // If only one group (Campus+Program), we can show a funnel chart
        // For multiple groups, it might be messy.
        // Let's summarize across all filtered groups for the chart
        let summary = {
            "Submitted": 0,
            "Selected": 0,
            "Waitlisted": 0,
            "Rejected": 0,
            "Offer Issued": 0,
            "Offer Accepted": 0,
            "Offer Declined": 0,
            "Offer Expired": 0,
            "Confirmation Fee Paid": 0,
        };

        result.forEach(row => {
            if (row.stage && summary.hasOwnProperty(row.stage)) {
                summary[row.stage] += row.count;
            }
        });

        if (summary.Submitted === 0) return null;

        const labels = Object.keys(summary);

        // To get multi-colored vertical bars in Frappe Charts, we use the multiple-dataset + stacking trick.
        // We use null instead of 0 to see if the chart engine omits them from the tooltip.
        const datasets = labels.map((label, i) => {
            return {
                name: label,
                values: labels.map((l, j) => (i === j ? summary[label] : null))
            };
        });

        return {
            data: {
                labels: labels,
                datasets: datasets
            },
            type: 'bar',
            height: 300,
            barOptions: {
                stacked: 1,
                space_between_bars: 20
            },
            colors: ['#007bff', '#28a745', '#ffc107', '#dc3545', '#17a2b8', '#6610f2', '#e83e8c', '#fd7e14', '#20c997']
        };
    }
};
