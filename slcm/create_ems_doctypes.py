import frappe

def create_or_update_doctype(doc_dict):
    if frappe.db.exists("DocType", doc_dict["name"]):
        print(f"Updating DocType: {doc_dict['name']}")
        doc = frappe.get_doc("DocType", doc_dict["name"])
        doc.update(doc_dict)
        doc.save(ignore_permissions=True)
    else:
        print(f"Creating DocType: {doc_dict['name']}")
        doc = frappe.get_doc(doc_dict)
        doc.insert(ignore_permissions=True)
    
    # Add System Manager permissions if not present
    if not any(perm.role == "System Manager" for perm in doc.permissions):
        doc.append("permissions", {
            "role": "System Manager",
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1,
            "submit": 0,
            "cancel": 0,
            "amend": 0,
            "report": 1,
            "share": 1,
            "print": 1,
            "email": 1
        })
        doc.save(ignore_permissions=True)

def setup_ems_doctypes():
    frappe.flags.in_patch = True # Allow creating custom doctypes without developer mode error depending on instance type
    
    # 1. Exam Component (New)
    create_or_update_doctype({
        "doctype": "DocType",
        "name": "Exam Component",
        "module": "SLCM",
        "custom": 0,
        "naming_rule": "By fieldname",
        "autoname": "field:component_name",
        "fields": [
            {
                "fieldname": "component_name",
                "label": "Component Name",
                "fieldtype": "Data",
                "reqd": 1,
                "unique": 1,
                "in_list_view": 1
            }
        ]
    })

    # 2. Exam Assessment (Update)
    exam_assessment = frappe.get_doc("DocType", "Exam Assessment")
    
    # Check if component_type exists, if not inject it
    if not any(f.fieldname == 'component_type' for f in exam_assessment.fields):
        exam_assessment.append("fields", {
            "fieldname": "component_type",
            "label": "Component Type",
            "fieldtype": "Link",
            "options": "Exam Component",
            "reqd": 1,
            "in_list_view": 1,
            "insert_after": "assessment_name"
        })
        exam_assessment.save(ignore_permissions=True)
        print("Updated Exam Assessment with Component Type")

    # 3. Exam type (Update)
    exam_type = frappe.get_doc("DocType", "Exam Type")
    if not any(f.fieldname == 'description' for f in exam_type.fields):
        exam_type.append("fields", {
            "fieldname": "description",
            "label": "Description",
            "fieldtype": "Small Text"
        })
        exam_type.save(ignore_permissions=True)
        print("Updated Exam Type with Description")

    # 4. Examination Plan (Update)
    exam_plan = frappe.get_doc("DocType", "Examination Plan")
    exam_plan_fields = [f.fieldname for f in exam_plan.fields]

    if "academic_year" not in exam_plan_fields:
        exam_plan.append("fields", {
            "fieldname": "academic_year",
            "label": "Academic Year",
            "fieldtype": "Link",
            "options": "Academic Year",
            "reqd": 1,
            "in_list_view": 1
        })
    if "exam_type" not in exam_plan_fields:
        exam_plan.append("fields", {
            "fieldname": "exam_type",
            "label": "Exam Type",
            "fieldtype": "Link",
            "options": "Exam Type",
            "reqd": 1,
            "in_list_view": 1
        })
    if "status" not in exam_plan_fields:
        exam_plan.append("fields", {
            "fieldname": "status",
            "label": "Status",
            "fieldtype": "Select",
            "options": "Draft\nActive\nCompleted",
            "default": "Draft",
            "reqd": 1,
            "in_list_view": 1
        })
    exam_plan.save(ignore_permissions=True)
    print("Updated Examination Plan with Academic Year, Exam Type, and Status")

    # 5. Exam Schema Weightage (Child Table)
    create_or_update_doctype({
        "doctype": "DocType",
        "name": "Exam Schema Weightage",
        "module": "SLCM",
        "custom": 0,
        "istable": 1,
        "fields": [
            {
                "fieldname": "exam_component",
                "label": "Exam Component",
                "fieldtype": "Link",
                "options": "Exam Component",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "weightage",
                "label": "Weightage (%)",
                "fieldtype": "Percent",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "effective_maximum_marks",
                "label": "Effective Maximum Marks",
                "fieldtype": "Float",
                "read_only": 1,
                "in_list_view": 1
            }
        ]
    })

    # 6. Exam Schema Assessment (Child Table)
    create_or_update_doctype({
        "doctype": "DocType",
        "name": "Exam Schema Assessment",
        "module": "SLCM",
        "custom": 0,
        "istable": 1,
        "fields": [
            {
                "fieldname": "exam_component",
                "label": "Exam Component",
                "fieldtype": "Link",
                "options": "Exam Component",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "assessment",
                "label": "Assessment",
                "fieldtype": "Link",
                "options": "Exam Assessment",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "minimum_marks",
                "label": "Minimum Marks",
                "fieldtype": "Float",
                "reqd": 1,
                "in_list_view": 1
            },
             {
                "fieldname": "maximum_marks",
                "label": "Maximum Marks",
                "fieldtype": "Float",
                "reqd": 1,
                "in_list_view": 1
            },
             {
                "fieldname": "passing_marks",
                "label": "Passing Marks",
                "fieldtype": "Float",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "weightage",
                "label": "Weightage (%)",
                "fieldtype": "Percent",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "requires_enrolment",
                "label": "Requires Enrolment",
                "fieldtype": "Check",
                "default": "0",
                "in_list_view": 1
            },
            {
                "fieldname": "effective_maximum_marks",
                "label": "Effective Maximum Marks",
                "fieldtype": "Float",
                "read_only": 1,
                "in_list_view": 1
            }
        ]
    })

    # 7. Exam Schema (Major Update)
    exam_schema = frappe.get_doc("DocType", "Exam Schema")
    fields_to_remove = ["internal_weightage", "external_weightage", "internals", "section_break_internals", "section_break_externals", "externals", "section_break_makeup", "makeup", "section_break_re_exam", "re_exam", "section_break_weightage"]
    
    # Remove old fields
    exam_schema.fields = [f for f in exam_schema.fields if f.fieldname not in fields_to_remove]

    # Add new table fields
    schema_fields = [f.fieldname for f in exam_schema.fields]
    
    if "requires_enrolment" not in schema_fields:
        exam_schema.append("fields", {
            "fieldname": "requires_enrolment",
            "label": "Requires Enrolment",
            "fieldtype": "Check",
            "default": "0"
        })
    if "section_break_weightage" not in schema_fields:
        exam_schema.append("fields", {
            "fieldname": "section_break_weightage",
            "label": "Weightage",
            "fieldtype": "Section Break"
        })
    if "weightages" not in schema_fields:
         exam_schema.append("fields", {
            "fieldname": "weightages",
            "label": "Weightages",
            "fieldtype": "Table",
            "options": "Exam Schema Weightage"
        })
    if "section_break_assessments" not in schema_fields:
        exam_schema.append("fields", {
            "fieldname": "section_break_assessments",
            "label": "Assessments",
            "fieldtype": "Section Break"
        })
    if "assessments" not in schema_fields:
        exam_schema.append("fields", {
            "fieldname": "assessments",
            "label": "Assessments",
            "fieldtype": "Table",
            "options": "Exam Schema Assessment"
        })
        
    exam_schema.save(ignore_permissions=True)
    print("Updated Exam Schema with new child tables")


    # 8. Grading Schema Component (Child Table)
    create_or_update_doctype({
        "doctype": "DocType",
        "name": "Grading Schema Component",
        "module": "SLCM",
        "custom": 0,
        "istable": 1,
        "fields": [
            {
                "fieldname": "grade",
                "label": "Grade",
                "fieldtype": "Data",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "marks_from",
                "label": "Marks From",
                "fieldtype": "Float",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "marks_to",
                "label": "Marks To",
                "fieldtype": "Float",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "grade_point",
                "label": "Grade Point",
                "fieldtype": "Float",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "failed",
                "label": "Failed",
                "fieldtype": "Check",
                "default": "0",
                "in_list_view": 1
            },
            {
                "fieldname": "consider_for_sgpa",
                "label": "Consider for SGPA",
                "fieldtype": "Check",
                "default": "1",
                "in_list_view": 1
            }
        ]
    })

    # 9. Grading Schema (New)
    create_or_update_doctype({
        "doctype": "DocType",
        "name": "Grading Schema",
        "module": "SLCM",
        "custom": 0,
        "naming_rule": "By fieldname",
        "autoname": "field:grading_schema_name",
        "fields": [
            {
                "fieldname": "grading_schema_name",
                "label": "Grading Schema Name",
                "fieldtype": "Data",
                "reqd": 1,
                "unique": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "maximum_marks",
                "label": "Maximum Marks",
                "fieldtype": "Float",
                "reqd": 1
            },
            {
                "fieldname": "grading_type",
                "label": "Grading Type",
                "fieldtype": "Select",
                "options": "Absolute\nRelative",
                "default": "Absolute",
                "reqd": 1
            },
            {
                "fieldname": "section_break_grades",
                "label": "Grades",
                "fieldtype": "Section Break"
            },
            {
                "fieldname": "grades",
                "label": "Grades",
                "fieldtype": "Table",
                "options": "Grading Schema Component",
                "reqd": 1
            }
        ]
    })

    # 10. Exam Course Mapping (New)
    create_or_update_doctype({
        "doctype": "DocType",
        "name": "Exam Course Mapping",
        "module": "SLCM",
        "custom": 0,
        "fields": [
            {
                "fieldname": "examination_plan",
                "label": "Examination Plan",
                "fieldtype": "Link",
                "options": "Examination Plan",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "course",
                "label": "Course",
                "fieldtype": "Link",
                "options": "Course",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "exam_schema",
                "label": "Exam Schema",
                "fieldtype": "Link",
                "options": "Exam Schema",
                "reqd": 1,
                "in_list_view": 1
            },
             {
                "fieldname": "grading_schema",
                "label": "Grading Schema",
                "fieldtype": "Link",
                "options": "Grading Schema",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "mapped_unmapped_status",
                "label": "Status",
                "fieldtype": "Select",
                "options": "Mapped\nUnmapped",
                "default": "Mapped",
                "in_list_view": 1
            }
        ]
    })

    frappe.db.commit()
    print("Successfully set up Examination Management System DocTypes.")

if __name__ == "__main__":
    setup_ems_doctypes()

