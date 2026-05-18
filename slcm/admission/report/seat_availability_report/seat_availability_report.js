frappe.query_reports["Seat Availability Report"] = {
    "filters": [
        {
            "fieldname": "campus",
            "label": __("Campus"),
            "fieldtype": "Link",
            "options": "Campus",
        },
        {
            "fieldname": "admission_year",
            "label": __("Admission Year"),
            "fieldtype": "Link",
            "options": "Admission Year",
            "default": frappe.defaults.get_user_default("admission_year")
        },
        {
            "fieldname": "admission_cycle",
            "label": __("Admission Cycle"),
            "fieldtype": "Link",
            "options": "Admission Cycle",
        },
        {
            "fieldname": "program",
            "label": __("Programme"),
            "fieldtype": "Link",
            "options": "Program",
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname == "vacant_seats" && data.vacant_seats > 0) {
            value = `<span style='color:green; font-weight:bold;'>${value}</span>`;
        }
        if (column.fieldname == "utilization_percent") {
            if (data.utilization_percent >= 100) {
                value = `<span style='color:blue; font-weight:bold;'>${value}</span>`;
            } else if (data.utilization_percent < 50) {
                value = `<span style='color:red;'>${value}</span>`;
            }
        }

        return value;
    }
};
