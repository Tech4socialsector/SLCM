frappe.query_reports["Monthly Venue Booking Report"] = {
    filters: [
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            options: [
                { value: "1",  label: __("January") },
                { value: "2",  label: __("February") },
                { value: "3",  label: __("March") },
                { value: "4",  label: __("April") },
                { value: "5",  label: __("May") },
                { value: "6",  label: __("June") },
                { value: "7",  label: __("July") },
                { value: "8",  label: __("August") },
                { value: "9",  label: __("September") },
                { value: "10", label: __("October") },
                { value: "11", label: __("November") },
                { value: "12", label: __("December") },
            ],
            default: String(frappe.datetime.now_date().split("-")[1]).replace(/^0/, ""),
            reqd: 1
        },
        {
            fieldname: "year",
            label: __("Year"),
            fieldtype: "Select",
            options: (function () {
                var opts = [];
                var y = new Date().getFullYear();
                for (var i = y - 2; i <= y + 1; i++) opts.push({ value: String(i), label: String(i) });
                return opts;
            })(),
            default: String(new Date().getFullYear()),
            reqd: 1
        },
        {
            fieldname: "status",
            label: __("Status"),
            fieldtype: "Select",
            options: "\nPending\nApproved\nRejected\nCancelled"
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
                "Approved":  "green",
                "Pending":   "orange",
                "Rejected":  "red",
                "Cancelled": "grey"
            };
            const c = colors[data.status];
            if (c) value = `<span class="indicator-pill ${c}">${data.status}</span>`;
        }
        return value;
    }
};
