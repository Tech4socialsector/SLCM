import frappe
import unittest


class TestProgramReservationPolicy(unittest.TestCase):

    def test_fields_exist(self):
        meta = frappe.get_meta("Program Reservation Policy")
        fields = [f.fieldname for f in meta.fields]
        for f in ["admission_cycle", "program", "total_seats", "status",
                  "total_allocated", "total_filled", "total_available", "categories"]:
            self.assertIn(f, fields)

    def test_category_child_has_fee(self):
        meta = frappe.get_meta("Program Reservation Category")
        fields = [f.fieldname for f in meta.fields]
        self.assertIn("application_fee", fields)

    def test_seat_sum_validation_blocks_excess(self):
        doc = frappe.new_doc("Program Reservation Policy")
        doc.total_seats = 100
        doc.append("categories", {"seats": 70, "application_fee": 500})
        doc.append("categories", {"seats": 50, "application_fee": 300})
        self.assertRaises(frappe.ValidationError, doc._validate_seat_sum)

    def test_seat_sum_validation_passes_within_limit(self):
        doc = frappe.new_doc("Program Reservation Policy")
        doc.total_seats = 100
        doc.append("categories", {"seats": 60, "application_fee": 500})
        doc.append("categories", {"seats": 40, "application_fee": 300})
        try:
            doc._validate_seat_sum()
        except frappe.ValidationError:
            self.fail("_validate_seat_sum raised unexpectedly")

    def test_get_fee_for_category_returns_correct_fee(self):
        doc = frappe.new_doc("Program Reservation Policy")
        doc.total_seats = 100
        doc.append("categories", {
            "category": "SC",
            "category_name": "Scheduled Caste",
            "seats": 27,
            "application_fee": 300
        })
        doc.append("categories", {
            "category": "GEN",
            "category_name": "General",
            "seats": 73,
            "application_fee": 1500
        })
        fee, label, cat = doc.get_fee_for_category("SC")
        self.assertEqual(fee, 300)

    def test_get_fee_falls_back_to_first_row(self):
        doc = frappe.new_doc("Program Reservation Policy")
        doc.total_seats = 100
        doc.append("categories", {
            "category_name": "General",
            "seats": 100,
            "application_fee": 1500
        })
        fee, label, cat = doc.get_fee_for_category(None)
        self.assertEqual(fee, 1500)
