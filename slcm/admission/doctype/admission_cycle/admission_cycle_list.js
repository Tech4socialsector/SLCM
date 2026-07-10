frappe.listview_settings["Admission Cycle"] = {
    // Ensure `status` is always fetched even if not in default field list
    add_fields: ["status"],

    get_indicator: function (doc) {
        // Use the custom `status` field instead of the Frappe docstatus-derived label.
        // This prevents "Cancelled" appearing when docstatus=2 but status="Closed".
        const color_map = {
            "Draft":  "gray",
            "Active": "green",
            "Closed": "red",
        };
        const status = doc.status || "Draft";
        return [__(status), color_map[status] || "gray", "status,=," + status];
    },

    formatters: {
        // Override the status column cell so it shows the field value with the
        // correct colour badge instead of Frappe's docstatus-derived "Cancelled".
        status: function (value, df, doc) {
            const color_map = {
                "Draft":  "gray",
                "Active": "green",
                "Closed": "red",
            };
            const status = value || "Draft";
            const color = color_map[status] || "gray";
            return `<span class="indicator-pill ${color}" style="font-size:12px;">${__(status)}</span>`;
        }
    },
};
