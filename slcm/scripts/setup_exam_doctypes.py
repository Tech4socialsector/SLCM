import frappe

def create_exam_type():
    if not frappe.db.exists("DocType", "Exam Type"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Exam Type",
            "module": "slcm",
            "custom": 0,
            "fields": [
                {
                    "fieldname": "exam_type",
                    "fieldtype": "Data",
                    "label": "Exam Type",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "belongs_in_re_exam_component",
                    "fieldtype": "Check",
                    "label": "Belongs In Re Exam Component",
                    "default": "0",
                    "in_list_view": 1
                }
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}],
            "autoname": "field:exam_type",
            "naming_rule": "By fieldname"
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        print("Exam Type DocType created.")
    else:
        print("Exam Type DocType already exists.")

def create_examination_plan():
    if not frappe.db.exists("DocType", "Examination Plan"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Examination Plan",
            "module": "slcm",
            "custom": 0,
            "fields": [
                {
                    "fieldname": "examination_name",
                    "fieldtype": "Data",
                    "label": "Examination Name",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "academic_term",
                    "fieldtype": "Link",
                    "options": "Academic Term",
                    "label": "Term",
                    "reqd": 1,
                    "in_list_view": 1
                }
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}],
            "autoname": "field:examination_name",
            "naming_rule": "By fieldname"
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        print("Examination Plan DocType created.")
    else:
        print("Examination Plan DocType already exists.")
