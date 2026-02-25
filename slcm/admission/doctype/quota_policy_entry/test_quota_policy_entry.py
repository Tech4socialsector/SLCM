import unittest

class TestQuotaPolicyEntry(unittest.TestCase):

    def test_child_table_structure(self):
        import frappe
        meta = frappe.get_meta("Quota Policy Entry")
        self.assertTrue(meta.istable)
        field_names = [f.fieldname for f in meta.fields]
        required = [
            "category_name", "category_code", "mandated_percentage",
            "mandated_seats", "legal_reference", "requires_certificate",
            "certificate_label", "is_income_based", "is_disability_based",
            "is_domicile_based"
        ]
        for f in required:
            self.assertIn(f, field_names, f"Missing field: {f}")
