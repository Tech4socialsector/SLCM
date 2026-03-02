import frappe
import unittest

class TestAdmissionCycleProgram(unittest.TestCase):

    def test_is_child_table(self):
        meta = frappe.get_meta("Admission Cycle Program")
        self.assertTrue(meta.istable)

    def test_required_fields(self):
        meta = frappe.get_meta("Admission Cycle Program")
        fieldnames = [f.fieldname for f in meta.fields]
        for f in ["program", "program_name", "campus",
                  "seats", "is_active", "eligibility_hint"]:
            self.assertIn(f, fieldnames)
