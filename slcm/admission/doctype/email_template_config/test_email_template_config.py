import frappe
import unittest

class TestEmailTemplateConfig(unittest.TestCase):
    def test_render_replaces_placeholders(self):
        doc = frappe.new_doc("Email Template Config")
        doc.template_name = "Test Template"
        doc.trigger_event = "Application Submitted"
        doc.subject = "Hello {{candidate_name}}"
        doc.body = "Your application {{applicant_id}} for {{program}} is received."
        doc.is_active = 1
        rendered = doc.render({
            "candidate_name": "Rahul",
            "applicant_id": "APP-001",
            "program": "BA LLB"
        })
        self.assertEqual(rendered["subject"], "Hello Rahul")
        self.assertIn("APP-001", rendered["body"])
