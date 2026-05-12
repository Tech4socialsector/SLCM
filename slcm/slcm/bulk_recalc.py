import frappe
from slcm.slcm.page.examination_result.examination_result import _recalculate_student_marks

def execute():
    updated = 0
    records = frappe.get_all("Student Course Marks", fields=["name", "course", "exam_plan"], filters={"status": ["!=", ""]})
    for r in records:
        try:
            _recalculate_student_marks(r.name, r.course, r.exam_plan)
            updated += 1
        except Exception as e:
            print(f"Error recalculating {r.name}: {e}")
    print(f"Successfully recalcuated {updated} records.")
