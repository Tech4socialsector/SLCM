# Copyright (c) 2026, TFSS and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestRefundTransaction(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Refund Transaction")
		frappe.db.delete("Refund Request")
		frappe.db.delete("Applicant", {"name": ["like", "TEST-APP-%"]})

		self.applicant = frappe.get_doc({
			"doctype": "Applicant",
			"name": "TEST-APP-002",
			"candidate_name": "Test Applicant Transaction",
			"email": "txn@example.com",
			"mobile_number": "1234567891",
			"program": "Computer Science",
			"campus": "SHC",
			"admission_cycle": "June To December",
			"academic_year": "2026",
			"status": "Fee Paid"
		})
		self.applicant.db_insert()

		# Create Refund Request
		self.refund_request = frappe.get_doc({
			"doctype": "Refund Request",
			"applicant": self.applicant.name,
			"status": "Approved",
			"refund_type": "Full",
			"amount_paid": 50000.0,
			"refund_amount": 50000.0,
			"razorpay_payment_id": "pay_12345",
			"refund_reason": "Test Transaction"
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def test_refund_transaction_creation(self):
		txn = frappe.get_doc({
			"doctype": "Refund Transaction",
			"refund_request": self.refund_request.name,
			"status": "Processed",
			"transaction_reference": "ref_9999"
		}).insert(ignore_permissions=True)

		self.assertEqual(txn.razorpay_payment_id, "pay_12345")
		self.assertEqual(txn.refund_amount, 50000.0)


def run_tests():
	import unittest
	suite = unittest.TestLoader().loadTestsFromTestCase(TestRefundTransaction)
	unittest.TextTestRunner(verbosity=2).run(suite)
