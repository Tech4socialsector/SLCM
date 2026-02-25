import frappe
import unittest

class TestComplianceReportConfig(unittest.TestCase):

    def setUp(self):
        self.doc_name = "Test RTI Report"

    def _make(self, report_type, mode):
        return frappe.get_doc({
            "doctype": "Compliance Report Config",
            "report_name": self.doc_name,
            "report_type": report_type,
            "compliance_mode": mode,
            "output_format": "Excel"
        })

    def test_rti_india_mode_allowed(self):
        doc = self._make("RTI Response Export", "India")
        doc.insert(ignore_permissions=True)
        self.assertTrue(frappe.db.exists("Compliance Report Config", self.doc_name))

    def test_rti_international_mode_blocked(self):
        doc = self._make("RTI Response Export", "International")
        self.assertRaises(frappe.ValidationError, doc.insert)

    def test_gdpr_india_mode_blocked(self):
        doc = self._make("GDPR Personal Data Export", "India")
        self.assertRaises(frappe.ValidationError, doc.insert)

    def test_gdpr_international_mode_allowed(self):
        doc = self._make("GDPR Personal Data Export", "International")
        doc.insert(ignore_permissions=True)
        self.assertTrue(frappe.db.exists("Compliance Report Config", self.doc_name))

    def tearDown(self):
        if frappe.db.exists("Compliance Report Config", self.doc_name):
            frappe.delete_doc("Compliance Report Config", self.doc_name, ignore_permissions=True)
