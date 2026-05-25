# Copyright (c) 2026, TFSS and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

class TestAdmissionCycle(FrappeTestCase):
	def setUp(self):
		# Clean up existing test cycle logs, cycles, and child tables if any
		frappe.db.delete("Admission Cycle Audit Log", {"admission_cycle": ["like", "TEST-%"]})
		frappe.db.delete("Admission Cycle Program", {"parent": ["like", "TEST-%"]})
		frappe.db.delete("Admission Cycle Stage", {"parent": ["like", "TEST-%"]})
		frappe.db.delete("Entrance Test Details", {"parent": ["like", "TEST-%"]})
		frappe.db.delete("Admission Cycle", {"name": ["like", "TEST-%"]})
		frappe.db.commit()

	def tearDown(self):
		# Clean up
		frappe.db.delete("Admission Cycle Audit Log", {"admission_cycle": ["like", "TEST-%"]})
		frappe.db.delete("Admission Cycle Program", {"parent": ["like", "TEST-%"]})
		frappe.db.delete("Admission Cycle Stage", {"parent": ["like", "TEST-%"]})
		frappe.db.delete("Entrance Test Details", {"parent": ["like", "TEST-%"]})
		frappe.db.delete("Admission Cycle", {"name": ["like", "TEST-%"]})
		frappe.db.commit()

	def test_audit_log_on_create_and_update(self):
		# 1. Create a cycle
		cycle = frappe.get_doc({
			"doctype": "Admission Cycle",
			"cycle_name": "TEST-Cycle-2026",
			"cycle_code": "TEST-TC26",
			"admission_year": "2026-27",
			"academic_year": "2026-2027",
			"cycle_start_date": "2026-06-01",
			"cycle_end_date": "2026-12-31",
			"application_start_date": "2026-06-01",
			"application_end_date": "2026-07-31",
			"application_form_template": "Applicant Application Form",
			"email_template": "Application Submitted Email",
			"status": "Draft",
			"programs": [
				{
					"program": "MSC CS",
					"seats": 50,
					"is_active": 1,
					"campus": "National Law School of India University"
				}
			]
		})
		cycle.insert()
		
		# Verify that creation log was written
		creation_logs = frappe.get_all("Admission Cycle Audit Log", filters={
			"admission_cycle": cycle.name,
			"changed_field": "Admission Cycle",
			"new_value": "Created"
		})
		self.assertEqual(len(creation_logs), 1)
		self.assertIsNotNone(creation_logs[0].name)
		
		# 2. Update a field (e.g. cycle_end_date and remarks)
		cycle = frappe.get_doc("Admission Cycle", cycle.name)
		cycle.cycle_end_date = "2027-01-15"
		cycle.remarks = "Testing audit logs"
		cycle.save()
		
		# Verify field change logs
		end_date_logs = frappe.get_all("Admission Cycle Audit Log", filters={
			"admission_cycle": cycle.name,
			"changed_field": "Cycle End Date",
			"previous_value": "2026-12-31",
			"new_value": "2027-01-15",
			"change_type": "Deadline Change"
		})
		self.assertEqual(len(end_date_logs), 1)

		remarks_logs = frappe.get_all("Admission Cycle Audit Log", filters={
			"admission_cycle": cycle.name,
			"changed_field": "Remarks",
			"new_value": "Testing audit logs",
			"change_type": "Rule Change"
		})
		self.assertEqual(len(remarks_logs), 1)

		# 3. Modify child table (programs)
		# 3a. Add a new program row
		cycle = frappe.get_doc("Admission Cycle", cycle.name)
		cycle.append("programs", {
			"program": "5-Year B.A., LL.B. (Hons.)",
			"seats": 100,
			"is_active": 1,
			"campus": "National Law School of India University"
		})
		cycle.save()
		
		added_prog_logs = frappe.get_all("Admission Cycle Audit Log", filters={
			"admission_cycle": cycle.name,
			"changed_field": "Programmes: 5-Year B.A., LL.B. (Hons.)",
			"previous_value": "N/A",
			"change_type": "Stage Config Change"
		})
		self.assertEqual(len(added_prog_logs), 1)
		
		log_val = frappe.db.get_value("Admission Cycle Audit Log", added_prog_logs[0].name, "new_value")
		self.assertIn("Total seats: 100", log_val)

		# 3b. Modify seats of MSC CS program
		cycle = frappe.get_doc("Admission Cycle", cycle.name)
		for row in cycle.programs:
			if row.program == "MSC CS":
				row.seats = 60
		cycle.save()
		
		modified_prog_logs = frappe.get_all("Admission Cycle Audit Log", filters={
			"admission_cycle": cycle.name,
			"changed_field": "Programmes -> MSC CS -> Total seats",
			"previous_value": "50",
			"new_value": "60",
			"change_type": "Stage Config Change"
		})
		self.assertEqual(len(modified_prog_logs), 1)


def run_test():
	t = TestAdmissionCycle()
	t.setUp()
	try:
		t.test_audit_log_on_create_and_update()
		print("Test executed successfully and PASSED!")
		return "OK"
	except Exception as e:
		print("TEST FAILED:", e)
		print("Generated logs in DB:")
		import json
		logs = frappe.get_all("Admission Cycle Audit Log", filters={"admission_cycle": "TEST-Cycle-2026"}, fields=["admission_cycle", "changed_field", "previous_value", "new_value", "change_type"])
		print(json.dumps(logs, indent=2, default=str))
		raise
	finally:
		t.tearDown()
