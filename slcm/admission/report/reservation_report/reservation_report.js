// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.query_reports["Reservation Report"] = {
    "filters": [
        {
            "fieldname": "academic_year",
            "label": __("Academic Year"),
            "fieldtype": "Link",
            "options": "Academic Year",
            "default": frappe.defaults.get_user_default("academic_year")
        },
        {
            "fieldname": "admission_cycle",
            "label": __("Admission Cycle"),
            "fieldtype": "Link",
            "options": "Admission Cycle"
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
    "onload": function(report) {
        if (report.page && typeof report.page.set_title_sub === "function") {
            report.page.set_title_sub(
                __("This Reservation Report displays category-wise candidate counts for applicants who have passed Part A (Entrance Test).")
            );
        }
    }
};
