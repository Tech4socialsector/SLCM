import frappe
import unittest

class TestGDPRDataRequest(unittest.TestCase):

    def test_doctype_exists(self):
        meta = frappe.get_meta("GDPR Data Request")
        self.assertEqual(meta.name, "GDPR Data Request")

    def test_required_fields_exist(self):
        meta = frappe.get_meta("GDPR Data Request")
        field_names = [f.fieldname for f in meta.fields]
        for f in ["applicant", "applicant_email", "request_type", "status",
                  "requested_on", "audit_trail"]:
            self.assertIn(f, field_names)

    def test_is_submittable(self):
        meta = frappe.get_meta("GDPR Data Request")
        self.assertTrue(meta.is_submittable)
