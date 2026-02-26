import frappe
import unittest

class TestDocumentRequirementConfig(unittest.TestCase):
    def test_empty_requirements_blocked(self):
        doc = frappe.new_doc("Document Requirement Config")
        doc.program = "BA LLB"
        doc.quota_category = "All"
        self.assertRaises(frappe.ValidationError, doc.validate)

    def test_invalid_format_blocked(self):
        doc = frappe.new_doc("Document Requirement Config")
        doc.program = "BA LLB"
        doc.quota_category = "All"
        doc.append("document_requirements", {
            "document_name": "Test Doc",
            "document_code": "TEST",
            "is_mandatory": 1,
            "allowed_formats": "pdf,exe,bat"
        })
        self.assertRaises(frappe.ValidationError, doc.validate)
