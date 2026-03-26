import frappe

def create_payment_log_doctype():
    doctype_name = "FLE Payment Log"
    if frappe.db.exists("DocType", doctype_name):
        print(f"DocType {doctype_name} already exists.")
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": doctype_name,
        "module": "SLCM",
        "custom": 0,
        "autoname": "format:FPL-{YYYY}-{####}",
        "fields": [
            {
                "fieldname": "reference_no",
                "fieldtype": "Link",
                "label": "Reference No",
                "options": "Foundations for a Legal Education",
                "in_list_view": 1,
                "reqd": 1
            },
            {
                "fieldname": "full_name",
                "fieldtype": "Data",
                "label": "Name",
                "in_list_view": 1,
                "fetch_from": "reference_no.candidate_name"
            },
            {
                "fieldname": "email",
                "fieldtype": "Data",
                "label": "Email",
                "options": "Email",
                "fetch_from": "reference_no.email_address"
            },
            {
                "fieldname": "payment_status",
                "fieldtype": "Select",
                "label": "Payment Status",
                "options": "\nAuthorized\nCaptured\nFailed\nRefunded\nPending\nCancelled",
                "in_list_view": 1,
                "reqd": 1
            },
            {
                "fieldname": "paid_amount",
                "fieldtype": "Currency",
                "label": "Paid Amount",
                "in_list_view": 1
            },
            {
                "fieldname": "transaction_id",
                "fieldtype": "Data",
                "label": "Transaction ID",
                "in_list_view": 1
            },
            {
                "fieldname": "transaction_date",
                "fieldtype": "Datetime",
                "label": "Transaction Date"
            },
            {
                "fieldname": "account_number_or_upi_id",
                "fieldtype": "Data",
                "label": "Account Number or UPI ID"
            }
        ],
        "permissions": [
            {
                "role": "System Manager",
                "read": 1,
                "write": 1,
                "create": 1,
                "delete": 1
            }
        ],
        "is_submittable": 0,
        "track_changes": 1,
        "track_views": 1
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"DocType {doctype_name} created successfully.")
