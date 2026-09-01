import frappe
import json

def execute():
    try:
        recs = frappe.get_all("PACE Applicant Fee Assignment", filters={"status": "Paid", "razorpay_paid_amount": 0}, fields=["name", "status", "razorpay_paid_amount", "payment_request"], limit=3)
        print("ZERO AMOUNT REC:", recs)
        recs_pos = frappe.get_all("PACE Applicant Fee Assignment", filters={"status": "Paid", "razorpay_paid_amount": [">", 0]}, fields=["name", "status", "razorpay_paid_amount", "payment_request"], limit=3)
        print("POSITIVE AMOUNT REC:", recs_pos)
    except Exception as e:
        print(str(e))
