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
            "options": "Programme",
        }
    ],
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "util" && data) {
            let color = data.util >= 90 ? "green" : (data.util >= 50 ? "orange" : "red");
            value = `<span style="color: ${color}; font-weight: bold;">${flt(data.util, 2)}%</span>`;
        }
        if (column.fieldname === "vacant_seats" && data && data.vacant_seats > 0) {
            value = `<span style="color: #d97706; font-weight: bold;">${data.vacant_seats}</span>`;
        }
        return value;
    },
    "onload": function(report) {
        if (report.page && typeof report.page.set_title_sub === "function") {
            report.page.set_title_sub(
                __("Category-wise seat capacity, allocated, waitlisted, vacant, and horizontal reservation breakdown.")
            );
        }
    }
};
