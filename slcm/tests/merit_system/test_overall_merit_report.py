# Copyright (c) 2026, TFSS and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from slcm.admission.report.overall_merit_report.overall_merit_report import execute, get_part_a_data, get_final_allotment_data

class TestOverallMeritReport(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.flags.ignore_links = True
        self.cycle = "2026-Test-Cycle"
        self.campus = "Test Campus"
        self.program = "Test Program"

        # Cleanup old test records
        frappe.db.delete("Shortlisting Merit List", {"admission_cycle": self.cycle})
        frappe.db.delete("Merit List", {"admission_cycle": self.cycle})

    def tearDown(self):
        frappe.flags.ignore_links = False
        frappe.db.delete("Shortlisting Merit List", {"admission_cycle": self.cycle})
        frappe.db.delete("Merit List", {"admission_cycle": self.cycle})
        super().tearDown()

    def test_part_a_data_filters_superseded(self):
        # Create superseded Shortlisting Merit List
        old_sp = frappe.get_doc({
            "doctype": "Shortlisting Merit List",
            "admission_cycle": self.cycle,
            "campus": self.campus,
            "program_level": "Undergraduate",
            "program": self.program,
            "status": "Superseded",
            "shortlist_applicants": [
                {
                    "applicant_id": "APP-OLD-001",
                    "candidate_name": "Old Candidate",
                    "program": self.program,
                    "actual_category": "General",
                    "nlsat_part_a_score": 50.0,
                    "shortlist_rank": 1,
                    "shortlist_status": "Shortlisted"
                }
            ]
        }).insert(ignore_permissions=True, ignore_links=True)

        # Create active Shortlisting Merit List
        new_sp = frappe.get_doc({
            "doctype": "Shortlisting Merit List",
            "admission_cycle": self.cycle,
            "campus": self.campus,
            "program_level": "Undergraduate",
            "program": self.program,
            "status": "Allocated",
            "shortlist_applicants": [
                {
                    "applicant_id": "APP-NEW-001",
                    "candidate_name": "New Candidate",
                    "program": self.program,
                    "actual_category": "General",
                    "nlsat_part_a_score": 80.0,
                    "shortlist_rank": 1,
                    "shortlist_status": "Shortlisted"
                }
            ]
        }).insert(ignore_permissions=True, ignore_links=True)

        filters = {
            "admission_cycle": self.cycle,
            "campus": self.campus,
            "program": self.program,
            "merit_processing_stage": "Shortlisting Rank List"
        }

        columns, data, message, chart, summary = execute(filters)
        applicant_ids = [d.get("applicant_id") for d in data]

        self.assertIn("APP-NEW-001", applicant_ids)
        self.assertNotIn("APP-OLD-001", applicant_ids)

    def test_final_allotment_data_filters_superseded(self):
        # Create superseded Merit List
        old_ml = frappe.get_doc({
            "doctype": "Merit List",
            "admission_cycle": self.cycle,
            "campus": self.campus,
            "program_level": "Undergraduate",
            "program": self.program,
            "merit_processing_stage": "Final Allotment Ranking",
            "status": "Superseded",
            "generated_on": frappe.utils.now_datetime(),
            "merit_applicants": [
                {
                    "applicant_id": "APP-OLD-002",
                    "candidate_name": "Old Merit Candidate",
                    "program": self.program,
                    "actual_category": "General",
                    "entrance_score": 50.0,
                    "interview_score": 20.0,
                    "total_score": 70.0,
                    "overall_rank": 1,
                    "status": "Selected"
                }
            ]
        }).insert(ignore_permissions=True, ignore_links=True)

        # Create active Merit List
        new_ml = frappe.get_doc({
            "doctype": "Merit List",
            "admission_cycle": self.cycle,
            "campus": self.campus,
            "program_level": "Undergraduate",
            "program": self.program,
            "merit_processing_stage": "Final Allotment Ranking",
            "status": "Generated",
            "generated_on": frappe.utils.now_datetime(),
            "merit_applicants": [
                {
                    "applicant_id": "APP-NEW-002",
                    "candidate_name": "New Merit Candidate",
                    "program": self.program,
                    "actual_category": "General",
                    "entrance_score": 80.0,
                    "interview_score": 40.0,
                    "total_score": 120.0,
                    "overall_rank": 1,
                    "status": "Selected"
                }
            ]
        }).insert(ignore_permissions=True, ignore_links=True)

        filters = {
            "admission_cycle": self.cycle,
            "campus": self.campus,
            "program": self.program,
            "merit_processing_stage": "Final Allotment Ranking"
        }

        columns, data, message, chart, summary = execute(filters)
        applicant_ids = [d.get("applicant_id") for d in data]

        self.assertIn("APP-NEW-002", applicant_ids)
        self.assertNotIn("APP-OLD-002", applicant_ids)
