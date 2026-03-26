import frappe

def update_fle_payment_status():
    doc = frappe.get_doc("DocType", "Foundations for a Legal Education")
    for field in doc.fields:
        if field.fieldname == "payment_status":
            field.options = "Unpaid\nPayment Initiated\nAuthorized\nCaptured\nPaid\nPayment Failed\nFailed\nRefunded\nPending\nCancelled"
            break
    doc.save()
    frappe.db.commit()
    print("Updated payment_status options successfully.")
