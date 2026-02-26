import frappe
import unittest

class TestApplicantPortalConfig(unittest.TestCase):

    def test_singleton_exists(self):
        doc = frappe.get_single("Applicant Portal Config")
        self.assertEqual(doc.doctype, "Applicant Portal Config")

    def test_required_fields_present(self):
        meta = frappe.get_meta("Applicant Portal Config")
        fieldnames = [f.fieldname for f in meta.fields]
        for f in ["portal_title", "portal_active", "allow_edit_after_submit",
                  "skip_fee_check_for_testing", "enable_email_notifications",
                  "enable_portal_notifications", "progress_style"]:
            self.assertIn(f, fieldnames)
