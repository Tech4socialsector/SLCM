# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from unittest.mock import patch
from slcm.tests.payment.payment_test_base import PaymentTestBase
from slcm.pace.web_form.pace_application_form.pace_application_form import verify_pace_payment_signature
from slcm.api.razorpay_webhook import handle_razorpay_webhook
from slcm.api.service.fee_service import FeeService
import json

class TestPACAdmissionPayments(PaymentTestBase):
	def test_successful_admission_fee(self):
		"""TC-PAD-001: Successful PACE Admission Fee Payment"""
		papp = self.create_pace_application()
		afa = self.create_pace_applicant_fee_assignment(papp.name, fee_type="Course Fee", amount=15000)
		pr = self.create_payment_request("PACE Applicant Fee Assignment", afa.name, "order_pad_001", amount=15000)

		self.mock_razorpay(payment_data={
			"id": "pay_pad_001",
			"amount": 1500000,
			"currency": "INR",
			"order_id": "order_pad_001",
			"status": "captured"
		})
		self.mock_signature_verification()

		with patch("slcm.pace.web_form.pace_application_form.pace_application_form._pace_portal_user_owns_application", return_value=True):
			res = verify_pace_payment_signature(
				razorpay_payment_id="pay_pad_001",
				razorpay_order_id="order_pad_001",
				razorpay_signature="sig",
				assignment_name=afa.name
			)

		self.assertEqual(res.get("status"), "success")
		self.assertEqual(frappe.db.get_value("PACE Applicant Fee Assignment", afa.name, "status"), "Paid")
		self.assertEqual(frappe.db.get_value("PACE Application", papp.name, "status"), "Fee Paid")

		# Verify Receipt Generated
		receipts = frappe.get_all("PACE Receipt", filters={"pace_application": papp.name, "fee_type": "Course Fee"})
		self.assertEqual(len(receipts), 1)

	def test_webhook_only(self):
		"""TC-PAD-002: Webhook Only completes PACE Admission payment"""
		papp = self.create_pace_application()
		afa = self.create_pace_applicant_fee_assignment(papp.name, fee_type="Course Fee", amount=15000)
		pr = self.create_payment_request("PACE Applicant Fee Assignment", afa.name, "order_pad_002", amount=15000)

		payload = {
			"event": "payment.captured",
			"payload": {
				"payment": {
					"entity": {
						"id": "pay_pad_002",
						"amount": 1500000,
						"currency": "INR",
						"order_id": "order_pad_002",
						"status": "captured"
					}
				}
			}
		}

		with patch("frappe.request.get_data", return_value=json.dumps(payload).encode("utf-8")), \
			 patch("frappe.get_request_header", return_value=None), \
			 patch("slcm.pace.web_form.pace_application_form.pace_application_form._pace_portal_user_owns_application", return_value=True):
			handle_razorpay_webhook()

		self.assertEqual(frappe.db.get_value("PACE Applicant Fee Assignment", afa.name, "status"), "Paid")
		self.assertEqual(frappe.db.get_value("PACE Application", papp.name, "status"), "Fee Paid")
		receipts = frappe.get_all("PACE Receipt", filters={"pace_application": papp.name, "fee_type": "Course Fee"})
		self.assertEqual(len(receipts), 1)

	def test_scheduler_recovery(self):
		"""TC-PAD-003: Scheduler Recovery completes PACE Admission payment"""
		papp = self.create_pace_application()
		afa = self.create_pace_applicant_fee_assignment(papp.name, fee_type="Course Fee", amount=15000)
		pr = self.create_payment_request("PACE Applicant Fee Assignment", afa.name, "order_pad_003", amount=15000)

		from frappe.utils import add_to_date
		old_time = add_to_date(frappe.utils.now_datetime(), minutes=-20)
		frappe.db.sql("UPDATE `tabPayment Request` SET modified = %s WHERE name = %s", (old_time, pr.name))
		frappe.db.commit()

		self.mock_razorpay(payments_list=[{
			"id": "pay_pad_003",
			"amount": 1500000,
			"currency": "INR",
			"order_id": "order_pad_003",
			"status": "captured"
		}])

		with patch("slcm.pace.web_form.pace_application_form.pace_application_form._pace_portal_user_owns_application", return_value=True):
			FeeService.reconcile_pending_payments()

		self.assertEqual(frappe.db.get_value("PACE Applicant Fee Assignment", afa.name, "status"), "Paid")
		self.assertEqual(frappe.db.get_value("PACE Application", papp.name, "status"), "Fee Paid")
		receipts = frappe.get_all("PACE Receipt", filters={"pace_application": papp.name, "fee_type": "Course Fee"})
		self.assertEqual(len(receipts), 1)

	def test_duplicate_payment_attempt(self):
		"""TC-PAD-004: Duplicate payment attempt is blocked"""
		papp = self.create_pace_application()
		afa = self.create_pace_applicant_fee_assignment(papp.name, fee_type="Course Fee", amount=15000)
		pr = self.create_payment_request("PACE Applicant Fee Assignment", afa.name, "order_pad_004", amount=15000)

		# Make it already paid
		frappe.db.set_value("PACE Applicant Fee Assignment", afa.name, "status", "Paid")
		frappe.db.commit()

		self.mock_razorpay(payment_data={
			"id": "pay_pad_004",
			"amount": 1500000,
			"currency": "INR",
			"order_id": "order_pad_004",
			"status": "captured"
		})
		self.mock_signature_verification()

		with patch("slcm.pace.web_form.pace_application_form.pace_application_form._pace_portal_user_owns_application", return_value=True):
			res = verify_pace_payment_signature(
				razorpay_payment_id="pay_pad_004",
				razorpay_order_id="order_pad_004",
				razorpay_signature="sig",
				assignment_name=afa.name
			)

		self.assertEqual(res.get("status"), "success")
