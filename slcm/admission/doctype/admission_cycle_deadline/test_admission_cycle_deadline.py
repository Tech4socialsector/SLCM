import frappe
import unittest

class TestAdmissionCycleDeadline(unittest.TestCase):
    def test_start_before_end(self):
        doc = frappe.new_doc("Admission Cycle Deadline")
        doc.admission_cycle = "TEST-CYCLE"
        doc.deadline_type = "Application"
        doc.start_datetime = "2025-01-10 10:00:00"
        doc.end_datetime = "2025-01-05 10:00:00"
        self.assertRaises(frappe.ValidationError, doc.validate)
