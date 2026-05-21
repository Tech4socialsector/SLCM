frappe.query_reports["Student Selection Report"] = {
    "filters": [
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
            "options": "Admission Cycle"
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
            "label": __("Programme"),
            "fieldtype": "Link",
            "options": "Program"
        },
        {
            "fieldname": "vertical_category",
            "label": __("Vertical Category"),
            "fieldtype": "Link",
            "options": "Admission Category"
        },
        {
            "fieldname": "selection_status",
            "label": __("Selection Status"),
            "fieldtype": "Select",
            "options": "\nSelected\nWaitlisted\nRejected\nOffer Issued\nOffer Accepted\nAccepted\nFee Paid"
        }
    ]
};
