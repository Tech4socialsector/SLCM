import frappe
import json

def execute():
	applicant = frappe.get_doc("Applicant", "APP-2026-01232").as_dict()
	student = frappe.get_doc("Student Master", "STUD-2026-00011").as_dict()
	afa_records = frappe.get_all("Applicant Fee Assignment", filters={"applicant": "APP-2026-01232"}, fields=["*"])
	with open("/tmp/comparison.json", "w") as f:
		json.dump({"applicant": applicant, "student": student, "afa": afa_records}, f, default=str, indent=4)
