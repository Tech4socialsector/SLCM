import frappe
from slcm.slcm.page.term_result.term_result import download_consolidated_report

def execute():
    plan = frappe.db.get_value("Exam Plan")
    if plan:
        print(f"Executing for {plan}")
        download_consolidated_report(exam_plan=plan)
        print("Success!")
    else:
        print("No Plan")
