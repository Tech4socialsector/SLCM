import unittest
from frappe.model.document import Document

class TestExamScoreField(unittest.TestCase):

    def test_doctype_is_child_table(self):
        import frappe
        meta = frappe.get_meta("Exam Score Field")
        self.assertTrue(meta.istable)

    def test_required_fields_exist(self):
        import frappe
        meta = frappe.get_meta("Exam Score Field")
        field_names = [f.fieldname for f in meta.fields]
        for required in ["field_name", "label", "field_type", "is_rank_field", "is_primary_score"]:
            self.assertIn(required, field_names)
