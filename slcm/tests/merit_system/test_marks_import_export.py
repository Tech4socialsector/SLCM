# Copyright (c) 2026, TFSS and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from slcm.admission.utils.entrance_test_marks_manager import (
    export_entrance_test_marks_template,
    import_entrance_test_marks_file,
    TEMPLATE_COLUMNS
)


class TestEntranceTestMarksImportExport(IntegrationTestCase):
    """
    Unit tests for Custom Entrance Test Marks Import & Export process.
    """

    def setUp(self):
        super().setUp()
        frappe.flags.ignore_links = True
        
        # Mock global search updates to avoid Redis connection errors in test environment
        from frappe.model import document as doc_mod
        self._orig_update_global_search = doc_mod.update_global_search
        doc_mod.update_global_search = lambda *args, **kwargs: None

        self.app_no_1 = "APP-TEST-EXP-001"
        self.app_no_2 = "APP-TEST-EXP-002"

        for app_id in [self.app_no_1, self.app_no_2]:
            if not frappe.db.exists("Applicant", app_id):
                app_doc = frappe.get_doc({
                    "doctype": "Applicant",
                    "candidate_name": "Test Candidate",
                    "email": f"{app_id}@example.com",
                    "whether_scstobc_ncl": "NA",
                    "program": "BA LLB",
                    "academic_year": "2026",
                    "admission_cycle": "2026",
                    "campus": "Main Campus"
                })
                app_doc.name = app_id
                app_doc.db_insert()

        # Create applicant 1 seat allocation
        if not frappe.db.exists("Entrance Test Seat Allocation", {"applicant": self.app_no_1}):
            doc1 = frappe.get_doc({
                "doctype": "Entrance Test Seat Allocation",
                "applicant": self.app_no_1,
                "candidate_name": "Candidate One",
                "academic_year": "2026",
                "admission_cycle": "2026",
                "campus": "Main Campus",
                "program_level": "Undergraduate",
                "program": "BA LLB",
                "entrance_test_list": "TEST-LIST-001",
                "seat_number": "SEAT-001",
                "shortlisted_status": "Shortlisted",
                "part_a_total_marks_scored": 75.0,
                "part_b_total_marks_scored": 40.0
            })
            doc1.flags.ignore_links = True
            doc1.flags.ignore_mandatory = True
            doc1.insert(ignore_permissions=True)
            self.alloc1 = doc1
        else:
            self.alloc1 = frappe.get_doc("Entrance Test Seat Allocation", {"applicant": self.app_no_1})

        # Create applicant 2 seat allocation (not shortlisted)
        if not frappe.db.exists("Entrance Test Seat Allocation", {"applicant": self.app_no_2}):
            doc2 = frappe.get_doc({
                "doctype": "Entrance Test Seat Allocation",
                "applicant": self.app_no_2,
                "candidate_name": "Candidate Two",
                "academic_year": "2026",
                "admission_cycle": "2026",
                "campus": "Main Campus",
                "program_level": "Undergraduate",
                "program": "BA LLB",
                "entrance_test_list": "TEST-LIST-001",
                "seat_number": "SEAT-002",
                "shortlisted_status": "",
                "part_a_total_marks_scored": 50.0
            })
            doc2.flags.ignore_links = True
            doc2.flags.ignore_mandatory = True
            doc2.insert(ignore_permissions=True)
            self.alloc2 = doc2
        else:
            self.alloc2 = frappe.get_doc("Entrance Test Seat Allocation", {"applicant": self.app_no_2})
        frappe.db.set_value("Entrance Test Seat Allocation", self.alloc2.name, "shortlisted_status", "No")



    def tearDown(self):
        super().tearDown()
        frappe.flags.ignore_links = False
        frappe.flags.ignore_mandatory = False
        frappe.db.delete("Entrance Test Seat Allocation", {"applicant": ["in", [self.app_no_1, self.app_no_2]]})
        
        # Restore global search updates
        from frappe.model import document as doc_mod
        doc_mod.update_global_search = self._orig_update_global_search

    def test_export_template_columns(self):
        """Test exporting marks template returns exact 10 columns."""
        res = export_entrance_test_marks_template(
            academic_year="2026",
            admission_cycle="2026",
            campus="Main Campus",
            program_level="Undergraduate",
            file_format="csv"
        )
        assert "file_url" in res
        assert res["file_url"].endswith(".csv")

        # Verify CSV header contains exact 10 columns
        file_doc = frappe.get_doc("File", {"file_url": res["file_url"]})
        content = file_doc.get_content()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        lines = content.strip().split("\n")
        header_cols = [c.strip('"').strip("\r").strip() for c in lines[0].split(",")]

        assert header_cols == TEMPLATE_COLUMNS

    def test_export_shortlisted_only(self):
        """Test exporting with shortlisted_only=True returns only shortlisted applicants."""
        res = export_entrance_test_marks_template(
            academic_year="2026",
            admission_cycle="2026",
            campus="Main Campus",
            program_level="Undergraduate",
            shortlisted_only=True,
            file_format="csv"
        )
        file_doc = frappe.get_doc("File", {"file_url": res["file_url"]})
        content = file_doc.get_content()
        if isinstance(content, bytes):
            content = content.decode("utf-8")

        assert self.app_no_1 in content
        assert self.app_no_2 not in content

    def test_import_part_a_and_part_b_non_destructive(self):
        """Test importing Part A and Part B marks updates DB without overwriting existing data with blanks."""
        csv_content = (
            "Application Number,Applicant Name,Program,Entrance Test Status,Shortlisted,Part A Marks,Part B Marks,Status\n"
            f"{self.app_no_1},Candidate One,BA LLB,Present,Yes,88.5,,Pass\n"
            f"{self.app_no_2},Candidate Two,BA LLB,Present,No,,65.0,Pass\n"
        )

        saved_file = frappe.utils.file_manager.save_file(
            "test_import_marks.csv",
            csv_content.encode("utf-8"),
            "Entrance Test Seat Allocation",
            self.alloc1.name,
            is_private=1
        )

        import_res = import_entrance_test_marks_file(file_url=saved_file.file_url)

        assert import_res["success_count"] == 2
        assert import_res["updated_count"] == 2
        assert import_res["error_count"] == 0

        # Reload records and check
        doc1 = frappe.get_doc("Entrance Test Seat Allocation", self.alloc1.name)
        assert doc1.part_a_total_marks_scored == 88.5
        # Part B should NOT be overwritten with blank; stays original 40.0
        assert doc1.part_b_total_marks_scored == 40.0
        assert doc1.total_marks_secured_in_part_a_b == 128.5

        doc2 = frappe.get_doc("Entrance Test Seat Allocation", self.alloc2.name)
        # Part A should NOT be overwritten with blank; stays original 50.0
        assert doc2.part_a_total_marks_scored == 50.0
        assert doc2.part_b_total_marks_scored == 65.0
        assert doc2.total_marks_secured_in_part_a_b == 115.0
