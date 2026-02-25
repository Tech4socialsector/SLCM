import frappe
import unittest

class TestExamTypeConfig(unittest.TestCase):

    def setUp(self):
        if not frappe.db.exists("Exam Type Config", "TEST-EXAM"):
            doc = frappe.get_doc({
                "doctype": "Exam Type Config",
                "exam_name": "Test Exam",
                "exam_code": "TEST-EXAM",
                "exam_category": "Institution-Own",
                "score_import_method": "Manual Entry",
                "validity_years": 1
            })
            doc.insert(ignore_permissions=True)

    def test_exam_type_created(self):
        self.assertTrue(frappe.db.exists("Exam Type Config", "TEST-EXAM"))

    def test_duplicate_score_field_names_blocked(self):
        doc = frappe.get_doc("Exam Type Config", "TEST-EXAM")
        doc.append("score_fields", {"field_name": "score", "label": "Score", "field_type": "Float"})
        doc.append("score_fields", {"field_name": "score", "label": "Score Duplicate", "field_type": "Float"})
        self.assertRaises(frappe.ValidationError, doc.save)

    def test_api_endpoint_required_for_api_method(self):
        doc = frappe.get_doc("Exam Type Config", "TEST-EXAM")
        doc.score_import_method = "API Integration"
        doc.api_endpoint = ""
        self.assertRaises(frappe.ValidationError, doc.save)

    def tearDown(self):
        frappe.db.delete("Exam Type Config", "TEST-EXAM")
