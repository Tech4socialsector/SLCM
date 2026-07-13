import frappe
import unittest


class TestProgrammeReservationCategory(unittest.TestCase):

    def test_is_child_table(self):
        self.assertTrue(frappe.get_meta("Programme Reservation Category").istable)

    def test_required_fields(self):
        meta = frappe.get_meta("Programme Reservation Category")
        fieldnames = [f.fieldname for f in meta.fields]
        for f in ["category", "category_name", "seats",
                  "filled_seats", "available_seats", "application_fee"]:
            self.assertIn(f, fieldnames)
