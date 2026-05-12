frappe.query_reports["Overall Merit Report"] = {
    "filters": [
        {
            "fieldname": "admission_cycle",
            "label": __("Admission Cycle"),
            "fieldtype": "Link",
            "options": "Admission Cycle",
            "reqd": 1
        },
        {
            "fieldname": "campus",
            "label": __("Campus"),
            "fieldtype": "Link",
            "options": "Campus",
            "reqd": 1
        },
        {
            "fieldname": "program",
            "label": "Programme",
            "fieldtype": "Link",
            "options": "Program"
        }

    ]
};
