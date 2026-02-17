frappe.query_reports["Overall Merit Report"] = {
    "filters": [
        {
            "fieldname": "admission_cycle",
            "label": __("Admission Cycle"),
            "fieldtype": "Link",
            "options": "test Admission Cycle",
            "reqd": 1
        },
        {
            "fieldname": "campus",
            "label": __("Campus"),
            "fieldtype": "Link",
            "options": "test Campus",
            "reqd": 1
        },
        {
            "fieldname": "program",
            "label": __("Program"),
            "fieldtype": "Link",
            "options": "test Program"
        },
        {
            "fieldname": "category",
            "label": __("Category"),
            "fieldtype": "Select",
            "options": "\nGEN\nOBC\nSC\nST\nEWS\nPwD"
        }
    ]
};
