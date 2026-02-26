import frappe
import unittest

class TestApplicationFormResponse(unittest.TestCase):

    def test_required_fields(self):
        meta = frappe.get_meta("Application Form Response")
        fieldnames = [f.fieldname for f in meta.fields]
        for f in ["applicant", "admission_cycle", "form_config",
                  "is_draft", "responses", "submitted_on", "last_saved_on"]:
            self.assertIn(f, fieldnames)

    def test_invalid_json_blocked(self):
        doc = frappe.new_doc("Application Form Response")
        doc.applicant = "TEST"
        doc.admission_cycle = "TEST"
        doc.form_config = "TEST"
        doc.responses = "not json {{{"
        self.assertRaises(frappe.ValidationError, doc.save)
