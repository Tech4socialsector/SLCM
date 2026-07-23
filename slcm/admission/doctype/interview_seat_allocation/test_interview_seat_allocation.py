# Copyright (c) 2026, TFSS and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

class TestInterviewSeatAllocation(FrappeTestCase):
    def setUp(self):
        # Create Academic Year
        if not frappe.db.exists("Academic Year", "2026-27"):
            frappe.get_doc({
                "doctype": "Academic Year",
                "academic_year_name": "2026-27",
            }).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

        # Create Campus
        if not frappe.db.exists("Campus", "Bengaluru"):
            frappe.get_doc({
                "doctype": "Campus",
                "campus_name": "Bengaluru",
            }).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

        # Create Admission Cycle
        if not frappe.db.exists("Admission Cycle", "Test Cycle - Applicant"):
            frappe.get_doc({
                "doctype": "Admission Cycle",
                "cycle_name": "Test Cycle - Applicant",
            }).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

        # Create Interview List
        iv_list_name = frappe.db.get_value("Interview List", {"academic_year": "2026-27", "campus": "Bengaluru", "admission_cycle": "Test Cycle - Applicant"})
        if not iv_list_name:
            iv_list = frappe.get_doc({
                "doctype": "Interview List",
                "academic_year": "2026-27",
                "campus": "Bengaluru",
                "admission_cycle": "Test Cycle - Applicant",
                "program_level": "Postgraduate",
                "status": "Generated"
            })
            iv_list.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
            iv_list_name = iv_list.name
        self.interview_list_name = iv_list_name

        # Create a Programme for testing
        if not frappe.db.exists("Programme", "TPA-2026-27-SEMESTER-1"):
            frappe.get_doc({
                "doctype": "Programme",
                "program_name": "Test Program - Applicant",
                "program_code": "TPA",
                "program_abbreviation": "TPA",
                "academic_year": "2026-27",
                "academic_term": "Semester 1",
            }).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

        # Create Domestic Applicant
        if not frappe.db.exists("Applicant", "APP-TEST-DOMESTIC"):
            frappe.get_doc({
                "doctype": "Applicant",
                "first_name": "Domestic",
                "last_name": "Test",
                "foriegn_national": "No",
                "email": "domestic@test.com",
                "program": "TPA-2026-27-SEMESTER-1",
                "status": "Applied",
                "gender": "Male",
                "intake_type": "Direct Merit",
                "date_of_birth": "2000-01-01"
            }).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

        # Create International Applicant
        if not frappe.db.exists("Applicant", "APP-TEST-INTL"):
            frappe.get_doc({
                "doctype": "Applicant",
                "first_name": "Intl",
                "last_name": "Test",
                "foriegn_national": "Yes",
                "email": "intl@test.com",
                "program": "TPA-2026-27-SEMESTER-1",
                "status": "Applied",
                "gender": "Female",
                "intake_type": "Direct Merit",
                "date_of_birth": "2000-01-01"
            }).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

    def test_is_international_applicant_flag(self):
        # 1. Test domestic applicant
        domestic_app = frappe.db.get_value("Applicant", {"email": "domestic@test.com"}, "name")
        alloc_domestic = frappe.get_doc({
            "doctype": "Interview Seat Allocation",
            "applicant": domestic_app,
            "interview_list": self.interview_list_name,
            "academic_year": "2026-27",
            "admission_cycle": "Test Cycle - Applicant",
            "campus": "Bengaluru",
            "program_level": "Postgraduate",
            "candidate_name": "Domestic Test"
        })
        alloc_domestic.insert(ignore_permissions=True)
        self.assertEqual(alloc_domestic.is_international_applicant, 0)

        # 2. Test international applicant
        intl_app = frappe.db.get_value("Applicant", {"email": "intl@test.com"}, "name")
        alloc_intl = frappe.get_doc({
            "doctype": "Interview Seat Allocation",
            "applicant": intl_app,
            "interview_list": self.interview_list_name,
            "academic_year": "2026-27",
            "admission_cycle": "Test Cycle - Applicant",
            "campus": "Bengaluru",
            "program_level": "Postgraduate",
            "candidate_name": "Intl Test"
        })
        alloc_intl.insert(ignore_permissions=True)
        self.assertEqual(alloc_intl.is_international_applicant, 1)

        # Clean up
        alloc_domestic.delete()
        alloc_intl.delete()
