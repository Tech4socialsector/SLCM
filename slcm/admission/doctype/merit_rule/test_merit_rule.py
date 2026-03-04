# Copyright (c) 2026, TFSS and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from slcm.admission.doctype.merit_rule.merit_service import generate_merit_for_level


class TestMeritRule(FrappeTestCase):
	def test_minimum_marks_filtering(self):
		# Setup dummy cycle, campus, and program level
		cycle = "Test Cycle"
		campus = "Test Campus"
		program_level = "UG"

		# Create a Merit Rule with minimum_marks = 60
		rule = frappe.get_doc({
			"doctype": "Merit Rule",
			"rule_name": "Test Rule Min Marks",
			"admission_cycle": cycle,
			"program_level": program_level,
			"minimum_marks": 60,
			"version": 1,
			"is_active": 1,
			"approval_authority": "VC",
			"effective_from": "2026-01-01",
			"components": [
				{
					"component_type": "HSC Percentage",
					"weight": 100,
					"is_active": 1
				}
			]
		}).insert(ignore_permissions=True)

		# Create a Merit Rule Mapping
		mapping = frappe.get_doc({
			"doctype": "Merit Rule Mapping",
			"admission_cycle": cycle,
			"campus": campus,
			"program_level": program_level,
			"merit_rule": rule.name,
			"priority": 1,
			"is_active": 1
		}).insert(ignore_permissions=True)

		# Create applicants via Eligibility Result
		# App 1: Score 70 (Should be included)
		frappe.get_doc({
			"doctype": "Eligibility Result",
			"applicant_id": "APP-001",
			"candidate_name": "Applicant One",
			"program": "Test Program",
			"program_level": program_level,
			"hsc_percentage": 70,
			"admission_cycle": cycle,
			"campus": campus,
			"result_status": "Qualified"
		}).insert(ignore_permissions=True)

		# App 2: Score 50 (Should be excluded)
		frappe.get_doc({
			"doctype": "Eligibility Result",
			"applicant_id": "APP-002",
			"candidate_name": "Applicant Two",
			"program": "Test Program",
			"program_level": program_level,
			"hsc_percentage": 50,
			"admission_cycle": cycle,
			"campus": campus,
			"result_status": "Qualified"
		}).insert(ignore_permissions=True)

		# Generate Merit List
		merit_list = generate_merit_for_level(cycle, campus, program_level)

		# Verification
		applicants = [d.applicant_id for d in merit_list.merit_applicants]
		self.assertIn("APP-001", applicants)
		self.assertNotIn("APP-002", applicants)
		self.assertEqual(len(merit_list.merit_applicants), 1)

		# Cleanup (optional, FrappeTestCase usually handles DB rollback)
