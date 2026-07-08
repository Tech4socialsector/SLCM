import frappe
def run():
    doc = frappe.get_doc("Offer Letter", "OL-2026-01255")
    print(f"Fee Structure: {doc.fee_structure}")
    print(f"Payable Amount: {doc.payable_amount}")
