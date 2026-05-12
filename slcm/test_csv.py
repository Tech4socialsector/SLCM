import frappe
from slcm.slcm.page.term_result.term_result import download_consolidated_report

def run_test():
    plan = "Ay 2026 - 1st Trimester"
    try:
        download_consolidated_report(exam_plan=plan)
        import csv
        from io import StringIO
        from frappe.utils import cstr

        # simulate to_csv
        f = StringIO()
        writer = csv.writer(f)
        for r in frappe.response["result"]:
            writer.writerow([cstr(v) for v in r])
        out = f.getvalue()
        print("Success evaluating to_csv!", len(out))
        print("Snippet:", out[:100])
    except Exception as e:
        print("Error evaluating:")
        import traceback
        traceback.print_exc()
