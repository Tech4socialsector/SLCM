# Copyright (c) 2026, TFSS and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today
from unittest.mock import patch, MagicMock


class TestRefundRequest(FrappeTestCase):
	def setUp(self):
		# Clean up any leftover test data
		frappe.db.delete("Admission Cancellation")
		frappe.db.delete("Refund Request")
		frappe.db.delete("Refund Transaction")
		frappe.db.delete("Applicant Payment Receipt")
		frappe.db.delete("Applicant", {"name": ["like", "TEST-APP-%"]})
		frappe.db.delete("Refund Policy", {"name": ["like", "Test Policy%"]})

		# Create a test refund policy
		if not frappe.db.exists("Refund Policy", "Test Policy Partial"):
			frappe.get_doc({
				"doctype": "Refund Policy",
				"policy_name": "Test Policy Partial",
				"days_from_payment": 5,
				"refund_percentage": 50.0
			}).insert(ignore_permissions=True)

		# Create a test applicant
		self.applicant = frappe.get_doc({
			"doctype": "Applicant",
			"name": "TEST-APP-001",
			"candidate_name": "Test Applicant",
			"email": "test@example.com",
			"mobile_number": "1234567890",
			"program": "Computer Science",
			"campus": "SHC",
			"admission_cycle": "June To December",
			"academic_year": "2026",
			"status": "Fee Paid"
		})
		self.applicant.db_insert()

		# Create an Applicant Payment Receipt
		self.receipt = frappe.get_doc({
			"doctype": "Applicant Payment Receipt",
			"name": "TEST-APR-001",
			"applicant": self.applicant.name,
			"transaction_id": "TXN-12345",
			"total_amount": 50000.0,
			"net_amount": 50000.0,
			"payment_date": today(),
			"docstatus": 1
		})
		self.receipt.db_insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_full_refund_workflow(self):
		# 1. Create Admission Cancellation
		cancellation = frappe.get_doc({
			"doctype": "Admission Cancellation",
			"applicant": self.applicant.name,
			"cancellation_reason": "Personal reasons",
			"applicant_payment_receipt": self.receipt.name,
			"status": "Initiated"
		}).insert(ignore_permissions=True)

		# Verify Refund Request was auto-created and linked
		self.assertTrue(cancellation.refund_request)
		refund = frappe.get_doc("Refund Request", cancellation.refund_request)
		self.assertEqual(refund.status, "Draft")
		self.assertEqual(refund.amount_paid, 50000.0)
		# Starts as default "Partial" based on Fee Structure policies
		self.assertEqual(refund.refund_type, "Partial")
		self.assertEqual(refund.refund_amount, 35000.0)

		# Explicitly set to "Full" and save
		refund.refund_type = "Full"
		refund.save(ignore_permissions=True)
		self.assertEqual(refund.refund_amount, 50000.0)

		# 2. Approve the Refund Request
		refund.status = "Approved"
		refund.save(ignore_permissions=True)
		self.assertEqual(refund.approved_by, frappe.session.user)
		self.assertIsNotNone(refund.approval_date)

		# Verify Admission Cancellation status synced to Approved/Processing
		cancellation.reload()
		self.assertEqual(cancellation.status, "Approved")

		# 3. Process the Refund Request
		refund.status = "Processed"
		refund.save(ignore_permissions=True)

		# Verify Admission Cancellation is Completed
		cancellation.reload()
		self.assertEqual(cancellation.status, "Completed")

		# Verify Applicant Status is Withdrawn
		self.applicant.reload()
		self.assertEqual(self.applicant.status, "Withdrawn")

	def test_partial_refund_workflow(self):
		# Create Admission Cancellation
		cancellation = frappe.get_doc({
			"doctype": "Admission Cancellation",
			"applicant": self.applicant.name,
			"cancellation_reason": "Change of mind",
			"applicant_payment_receipt": self.receipt.name,
			"status": "Initiated"
		}).insert(ignore_permissions=True)

		refund = frappe.get_doc("Refund Request", cancellation.refund_request)
		
		# Set to Partial Refund and select the manually created policy
		refund.refund_type = "Partial"
		refund.refund_policy = "Test Policy Partial"
		refund.save(ignore_permissions=True)

		# 50% of 50000 should be 25000
		self.assertEqual(refund.refund_amount, 25000.0)

		# Approve and Process
		refund.status = "Approved"
		refund.save(ignore_permissions=True)
		refund.status = "Processed"
		refund.save(ignore_permissions=True)

		self.applicant.reload()
		self.assertEqual(self.applicant.status, "Withdrawn")

	def test_no_refund_workflow(self):
		# Create Admission Cancellation
		cancellation = frappe.get_doc({
			"doctype": "Admission Cancellation",
			"applicant": self.applicant.name,
			"cancellation_reason": "No show",
			"applicant_payment_receipt": self.receipt.name,
			"status": "Initiated"
		}).insert(ignore_permissions=True)

		refund = frappe.get_doc("Refund Request", cancellation.refund_request)
		
		# Set to No Refund
		refund.refund_type = "No Refund"
		refund.save(ignore_permissions=True)

		self.assertEqual(refund.refund_amount, 0.0)

		# Approve and Process
		refund.status = "Approved"
		refund.save(ignore_permissions=True)
		refund.status = "Processed"
		refund.save(ignore_permissions=True)

		self.applicant.reload()
		self.assertEqual(self.applicant.status, "Withdrawn")

	@patch('slcm.api.service.razorpay_utils.get_razorpay_client')
	def test_automated_razorpay_refund(self, mock_get_client):
		# Mock client and refund creation response
		mock_client = MagicMock()
		mock_get_client.return_value = mock_client
		mock_client.refund.create.return_value = {
			"id": "rfnd_12345",
			"payment_id": "pay_12345",
			"amount": 3500000,
			"status": "processed"
		}

		# Setup receipt with a razorpay payment ID (starts with pay_)
		frappe.db.set_value("Applicant Payment Receipt", self.receipt.name, "transaction_id", "pay_12345")
		self.receipt.reload()

		# Create Cancellation
		cancellation = frappe.get_doc({
			"doctype": "Admission Cancellation",
			"applicant": self.applicant.name,
			"cancellation_reason": "Personal reasons",
			"applicant_payment_receipt": self.receipt.name,
			"status": "Initiated"
		}).insert(ignore_permissions=True)

		refund = frappe.get_doc("Refund Request", cancellation.refund_request)
		self.assertEqual(refund.razorpay_payment_id, "pay_12345")

		# Shift to processed to trigger the mock Razorpay API call
		refund.status = "Processed"
		refund.save(ignore_permissions=True)

		# Verify API was called with the correct parameters (amount in paise) and idempotency key
		mock_client.refund.create.assert_called_once_with({
			"payment_id": "pay_12345",
			"amount": 3500000,  # 70% of 50000 is 35000, which is 3500000 paise
			"notes": {
				"refund_request": refund.name
			}
		}, {
			"X-Refund-Idempotency": refund.name
		})

		# Verify refund request got updated with the refund ID
		refund.reload()
		self.assertEqual(refund.razorpay_refund_id, "rfnd_12345")

		# Verify Refund Transaction was auto-created with Processed status
		txn_exists = frappe.db.exists("Refund Transaction", {
			"refund_request": refund.name,
			"status": "Processed",
			"razorpay_refund_id": "rfnd_12345"
		})
		self.assertTrue(txn_exists)

	def test_excessive_refund_prevention(self):
		# Create first partial refund (30000.0)
		cancellation1 = frappe.get_doc({
			"doctype": "Admission Cancellation",
			"applicant": self.applicant.name,
			"cancellation_reason": "Reason 1",
			"applicant_payment_receipt": self.receipt.name,
			"status": "Initiated"
		}).insert(ignore_permissions=True)

		refund1 = frappe.get_doc("Refund Request", cancellation1.refund_request)
		# Force a manual amount of 30,000 (valid since it's <= 50,000 amount paid)
		refund1.refund_type = "Partial"
		refund1.refund_amount = 30000.0
		refund1.save(ignore_permissions=True)

		# Create a second cancellation/refund request
		refund2 = frappe.get_doc({
			"doctype": "Refund Request",
			"applicant": self.applicant.name,
			"applicant_payment_receipt": self.receipt.name,
			"status": "Draft",
			"refund_type": "Partial",
			"amount_paid": 50000.0,
			"refund_amount": 30000.0,
			"refund_reason": "Reason 2"
		})

		# Saving should fail because 30,000 + 30,000 > 50,000
		self.assertRaises(frappe.ValidationError, refund2.insert)


def run_tests():
	import unittest
	suite = unittest.TestLoader().loadTestsFromTestCase(TestRefundRequest)
	unittest.TextTestRunner(verbosity=2).run(suite)

