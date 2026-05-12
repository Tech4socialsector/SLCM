
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
    ]
};
