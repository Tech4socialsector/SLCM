import frappe
import unittest

class TestQuotaPolicy(unittest.TestCase):

    def setUp(self):
        self.policy_name = "Test Quota Policy"

    def _make_policy(self, entries, is_legal_mandate=0):
        doc = frappe.get_doc({
            "doctype": "Quota Policy",
            "policy_name": self.policy_name,
            "is_legal_mandate": is_legal_mandate,
            "quota_entries": entries
        })
        return doc

    def test_policy_created_with_entries(self):
        doc = self._make_policy([
            {"category_name": "General", "category_code": "GEN", "mandated_percentage": 50},
            {"category_name": "SC", "category_code": "SC", "mandated_percentage": 15}
        ])
        doc.insert(ignore_permissions=True)
        self.assertTrue(frappe.db.exists("Quota Policy", self.policy_name))

    def test_duplicate_category_code_blocked(self):
        doc = self._make_policy([
            {"category_name": "SC", "category_code": "SC", "mandated_percentage": 15},
            {"category_name": "SC Duplicate", "category_code": "SC", "mandated_percentage": 10}
        ])
        self.assertRaises(frappe.ValidationError, doc.insert)

    def test_percentage_over_100_blocked(self):
        doc = self._make_policy([
            {"category_name": "General", "category_code": "GEN", "mandated_percentage": 60},
            {"category_name": "SC", "category_code": "SC", "mandated_percentage": 50}
        ])
        self.assertRaises(frappe.ValidationError, doc.insert)

    def test_empty_entries_blocked(self):
        doc = self._make_policy([])
        self.assertRaises(frappe.ValidationError, doc.insert)

    def tearDown(self):
        if frappe.db.exists("Quota Policy", self.policy_name):
            frappe.delete_doc("Quota Policy", self.policy_name, ignore_permissions=True)
