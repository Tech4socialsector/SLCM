import frappe
from slcm.slcm.page.examination_result.examination_result import _recalculate_student_marks

def execute():
    # Find the SCM
    scm_info = frappe.db.get_value("Student Course Marks", {"student": "BALLB25001", "exam_plan": "Ay 2026 - 1st Trimester"}, ["name", "course", "exam_plan"], as_dict=True)
    print(f"SCM Info: {scm_info}")
    if scm_info:
        res = _recalculate_student_marks(scm_info.name, scm_info.course, scm_info.exam_plan)
        print(f"Result: {res}")
        
        scm_doc = frappe.get_doc("Student Course Marks", scm_info.name)
        print(f"DB Updated Final Marks: {scm_doc.updated_final_marks}")
