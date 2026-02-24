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
            "fieldname": "program_level",
            "label": __("Program Level"),
            "fieldtype": "Select",
            "options": "UG\nPG\nResearch Course"
        },
        {
            "fieldname": "program",
            "label": __("Program"),
            "fieldtype": "Link",
            "options": "Program"
        },
        {
            "fieldname": "reservation_category",
            "label": __("Category"),
            "fieldtype": "Link",
            "options": "Admission Category"
        }
    ]
};
