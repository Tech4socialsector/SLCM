import frappe

def create_exam_assessment():
    if not frappe.db.exists("DocType", "Exam Assessment"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Exam Assessment",
            "module": "slcm",
            "istable": 1,
            "custom": 0,
            "fields": [
                {
                    "fieldname": "assessment_name",
                    "fieldtype": "Data",
                    "label": "Assessment Name",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "minimum_marks",
                    "fieldtype": "Float",
                    "label": "Minimum Marks",
                    "in_list_view": 1
                },
                {
                    "fieldname": "maximum_marks",
                    "fieldtype": "Float",
                    "label": "Maximum Marks",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "passing_marks",
                    "fieldtype": "Float",
                    "label": "Passing Marks",
                    "in_list_view": 1
                },
                {
                    "fieldname": "weightage",
                    "fieldtype": "Percent",
                    "label": "Weightage",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "requires_enrollment",
                    "fieldtype": "Check",
                    "label": "Requires Enrollment",
                    "default": "0",
                    "in_list_view": 1
                },
                {
                    "fieldname": "consider_for_final_status",
                    "fieldtype": "Check",
                    "label": "Consider For Final Status",
                    "default": "0"
                }
            ],
            "permissions": []
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        print("Exam Assessment DocType created.")
    else:
        print("Exam Assessment DocType already exists.")

def create_exam_schema():
    if not frappe.db.exists("DocType", "Exam Schema"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Exam Schema",
            "module": "slcm",
            "custom": 0,
            "fields": [
                {
                    "fieldname": "schema_name",
                    "fieldtype": "Data",
                    "label": "Schema Name",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "details",
                    "fieldtype": "Small Text",
                    "label": "Details"
                },
                {
                    "fieldname": "column_break_1",
                    "fieldtype": "Column Break"
                },
                {
                    "fieldname": "total_marks",
                    "fieldtype": "Float",
                    "label": "Total Marks",
                    "reqd": 1
                },
                {
                    "fieldname": "passing_marks",
                    "fieldtype": "Float",
                    "label": "Passing Marks",
                    "reqd": 1
                },
                {
                    "fieldname": "section_break_weightage",
                    "fieldtype": "Section Break",
                    "label": "Weightage"
                },
                {
                    "fieldname": "internal_weightage",
                    "fieldtype": "Percent",
                    "label": "Internal Weightage",
                    "reqd": 1
                },
                {
                    "fieldname": "column_break_2",
                    "fieldtype": "Column Break"
                },
                {
                    "fieldname": "external_weightage",
                    "fieldtype": "Percent",
                    "label": "External Weightage",
                    "reqd": 1
                },
                {
                    "fieldname": "section_break_internals",
                    "fieldtype": "Section Break",
                    "label": "Internals"
                },
                {
                    "fieldname": "internals",
                    "fieldtype": "Table",
                    "label": "Internals",
                    "options": "Exam Assessment"
                },
                {
                    "fieldname": "section_break_externals",
                    "fieldtype": "Section Break",
                    "label": "Externals"
                },
                {
                    "fieldname": "externals",
                    "fieldtype": "Table",
                    "label": "Externals",
                    "options": "Exam Assessment"
                },
                {
                    "fieldname": "section_break_makeup",
                    "fieldtype": "Section Break",
                    "label": "Makeup (Optional)"
                },
                {
                    "fieldname": "makeup",
                    "fieldtype": "Table",
                    "label": "Makeup",
                    "options": "Exam Assessment"
                },
                {
                    "fieldname": "section_break_re_exam",
                    "fieldtype": "Section Break",
                    "label": "Re-Exam (Optional)"
                },
                {
                    "fieldname": "re_exam",
                    "fieldtype": "Table",
                    "label": "Re-Exam",
                    "options": "Exam Assessment"
                }
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}],
            "autoname": "field:schema_name",
            "naming_rule": "By fieldname"
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        print("Exam Schema DocType created.")
    else:
        print("Exam Schema DocType already exists.")

def create_examination_plan_course():
    if not frappe.db.exists("DocType", "Examination Plan Course"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Examination Plan Course",
            "module": "slcm",
            "custom": 0,
            "fields": [
                {
                    "fieldname": "examination_plan",
                    "fieldtype": "Link",
                    "label": "Examination Plan",
                    "options": "Examination Plan",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "course",
                    "fieldtype": "Link",
                    "label": "Course",
                    "options": "Course",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "exam_schema",
                    "fieldtype": "Link",
                    "label": "Exam Schema",
                    "options": "Exam Schema",
                    "in_list_view": 1
                }
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}],
            "autoname": "format:EPC-{course}-{examination_plan}",
            "naming_rule": "Expression"
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        print("Examination Plan Course DocType created.")
    else:
        print("Examination Plan Course DocType already exists.")

if __name__ == "__main__":
    create_exam_assessment()
    create_exam_schema()
    create_examination_plan_course()
