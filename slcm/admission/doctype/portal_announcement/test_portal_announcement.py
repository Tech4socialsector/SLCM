import frappe
import unittest
from frappe.utils import add_days, now


class TestPortalAnnouncement(unittest.TestCase):

    def test_required_fields(self):
        meta = frappe.get_meta("Portal Announcement")
        fieldnames = [f.fieldname for f in meta.fields]
        for f in ["title", "announcement_type", "status", "show_on_portal",
                  "content", "publish_date", "expiry_date", "target_audience",
                  "event_date", "event_venue", "view_count"]:
            self.assertIn(f, fieldnames)

    def test_expiry_before_publish_blocked(self):
        doc = frappe.new_doc("Portal Announcement")
        doc.title = "Test"
        doc.announcement_type = "Announcement"
        doc.content = "Test content"
        doc.publish_date = now()
        doc.expiry_date = add_days(now(), -1)
        doc.target_audience = "Global"
        self.assertRaises(frappe.ValidationError, doc.validate)

    def test_status_options(self):
        meta = frappe.get_meta("Portal Announcement")
        field = next(f for f in meta.fields if f.fieldname == "status")
        options = field.options.split("
")
        self.assertIn("Draft", options)
        self.assertIn("Published", options)
        self.assertIn("Archived", options)
