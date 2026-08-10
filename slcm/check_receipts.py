
import frappe
def get_recent_receipts():
    receipts = frappe.get_all("Applicant Payment Receipt", filters={"offer_letter": "OL-2026-02668"}, fields=["name", "transaction_id", "fee_type", "total_amount"])
    errors = frappe.get_all("Error Log", limit=1, fields=["name", "method", "error"], order_by="creation desc")
    print("RECEIPTS_FOUND:", receipts)
    print("ERRORS_FOUND:", errors)

