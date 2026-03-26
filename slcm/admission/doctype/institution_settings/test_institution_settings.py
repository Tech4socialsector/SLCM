import frappe
import unittest

class TestInstitutionSettings(unittest.TestCase):

    def setUp(self):
        self.settings = frappe.get_single("Institution Settings")

    def test_single_doctype_exists(self):
        self.assertEqual(self.settings.doctype, "Institution Settings")

    def test_multi_campus_default_off(self):
        self.settings.enable_multi_campus = 0
        self.settings.save()
        val = frappe.db.get_single_value("Institution Settings", "enable_multi_campus")
        self.assertEqual(val, 0)

    def test_multi_campus_can_be_enabled(self):
        self.settings.enable_multi_campus = 1
        self.settings.max_campus_preferences = 3
        self.settings.save()
        val = frappe.db.get_single_value("Institution Settings", "enable_multi_campus")
        self.assertEqual(val, 1)

    def test_compliance_mode_default(self):
        self.settings.compliance_mode = "India"
        self.settings.save()
        val = frappe.db.get_single_value("Institution Settings", "compliance_mode")
        self.assertEqual(val, "India")

    def tearDown(self):
        self.settings.enable_multi_campus = 0
        self.settings.compliance_mode = "India"
        self.settings.save()
