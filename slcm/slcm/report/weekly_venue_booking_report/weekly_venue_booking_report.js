frappe.query_reports["Weekly Venue Booking Report"] = {
    filters: [
        {
            fieldname: "week_start",
            label: __("Any Date in Week"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1,
            description: __("Pick any date — the report shows Mon–Sun of that week")
        },
        {
            fieldname: "status",
            label: __("Status"),
            fieldtype: "Select",
            options: "\nPending Allotment\nAllotted\nRejected\nCancelled"
        },
        {
            fieldname: "requester_type",
            label: __("Requester Type"),
            fieldtype: "Select",
            options: "\nStudent\nFaculty\nStaff\nOther"
        },
        {
            fieldname: "room",
            label: __("Room"),
            fieldtype: "Link",
            options: "Room"
        }
    ],

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "status" && data) {
            const colors = {
                "Allotted":         "green",
                "Pending Allotment": "orange",
                "Rejected":         "red",
                "Cancelled":        "grey"
            };
            const c = colors[data.status];
            if (c) value = `<span class="indicator-pill ${c}">${data.status}</span>`;
        }
        if (column.fieldname === "day_label" && data) {
            value = `<strong>${value}</strong>`;
        }
        return value;
    }
};
