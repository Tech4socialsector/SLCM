import frappe
import unittest

class TestApplicantNotification(unittest.TestCase):

    def test_required_fields(self):
        meta = frappe.get_meta("Applicant Notification")
        fieldnames = [f.fieldname for f in meta.fields]
        for f in ["applicant", "notification_type", "is_read",
                  "created_on", "message", "action_url"]:
            self.assertIn(f, fieldnames)

    def test_notification_types(self):
        meta = frappe.get_meta("Applicant Notification")
        field = next((f for f in meta.fields if f.fieldname == "notification_type"), None)
        self.assertIsNotNone(field)
        options = field.options.split("\n")

        for t in ["Stage Update", "Document Request", "Offer", "Fee", "General"]:
            self.assertIn(t, options)
