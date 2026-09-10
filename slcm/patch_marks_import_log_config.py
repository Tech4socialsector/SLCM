import frappe

def execute():
    # 1. Update autoname for Marks Import Log
    log_dt = frappe.get_doc("DocType", "Marks Import Log")
    if log_dt.autoname != "format:IMP-LOG-.###":
        log_dt.autoname = "format:IMP-LOG-.###"
        log_dt.save()

    # 2. Update autoname for Marks Import Log Detail
    detail_dt = frappe.get_doc("DocType", "Marks Import Log Detail")
    if detail_dt.autoname != "format:{import_log}-.######":
        detail_dt.autoname = "format:{import_log}-.######"
        detail_dt.save()

    # 3. Add Configurable Exam Components
    has_exam_component = any(f.fieldname == 'exam_component' for f in log_dt.fields)
    if not has_exam_component:
        # We need to add Section Breaks and Fields
        log_dt.append("fields", {
            "fieldname": "exam_section",
            "fieldtype": "Section Break",
            "label": "Exam",
            "insert_after": "evaluation_schema"
        })
        log_dt.append("fields", {
            "fieldname": "exam_component",
            "fieldtype": "Link",
            "label": "Exam Component",
            "options": "Exam Component",
            "insert_after": "exam_section"
        })
        log_dt.append("fields", {
            "fieldname": "exam_column",
            "fieldtype": "Column Break",
            "insert_after": "exam_component"
        })
        log_dt.append("fields", {
            "fieldname": "assessment_type",
            "fieldtype": "Link",
            "label": "Assessment Type",
            "options": "Exam Assessment Type",
            "insert_after": "exam_column"
        })
        
        log_dt.append("fields", {
            "fieldname": "re_exam_section",
            "fieldtype": "Section Break",
            "label": "Re Exam",
            "insert_after": "assessment_type"
        })
        log_dt.append("fields", {
            "fieldname": "re_exam_component",
            "fieldtype": "Link",
            "label": "Exam Component",
            "options": "Exam Component",
            "insert_after": "re_exam_section"
        })
        log_dt.append("fields", {
            "fieldname": "re_exam_column",
            "fieldtype": "Column Break",
            "insert_after": "re_exam_component"
        })
        log_dt.append("fields", {
            "fieldname": "re_exam_assessment_type",
            "fieldtype": "Link",
            "label": "Assessment Type",
            "options": "Exam Assessment Type",
            "insert_after": "re_exam_column"
        })
        
        log_dt.save()
        frappe.db.commit()
        print("Patched Marks Import Log schema with config fields and updated autoname.")
    else:
        print("Schema already patched.")

