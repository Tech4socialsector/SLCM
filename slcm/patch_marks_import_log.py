import frappe

def execute():
    # Add exam_plan and evaluation_schema to Marks Import Log
    doc = frappe.get_doc("DocType", "Marks Import Log")
    
    has_exam_plan = any(f.fieldname == 'exam_plan' for f in doc.fields)
    has_evaluation_schema = any(f.fieldname == 'evaluation_schema' for f in doc.fields)
    
    if not has_exam_plan:
        doc.append("fields", {
            "fieldname": "exam_plan",
            "fieldtype": "Link",
            "label": "Exam Plan",
            "options": "Exam Plan",
            "insert_after": "import_file"
        })
        
    if not has_evaluation_schema:
        doc.append("fields", {
            "fieldname": "evaluation_schema",
            "fieldtype": "Link",
            "label": "Evaluation Schema",
            "options": "Evaluation Schema",
            "insert_after": "exam_plan"
        })
        
    if not has_exam_plan or not has_evaluation_schema:
        doc.save()
        frappe.db.commit()
        print("Patched Marks Import Log schema.")
    else:
        print("Schema already patched.")
