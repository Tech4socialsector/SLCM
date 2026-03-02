import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def execute():
    doctype = "Foundations for a Legal Education"
    
    # Check if doctype exists
    if not frappe.db.exists("DocType", doctype):
        print(f"DocType '{doctype}' does not exist.")
        return

    # Let's see if there is an existing standard field or custom field
    meta = frappe.get_meta(doctype)
    field = meta.get_field("payment_status")
    
    if field:
        print(f"Field 'payment_status' already exists with type '{field.fieldtype}' and options '{field.options}'")
        options = ["Pending", "Paid", "Failed", "Refunded", "Cancelled"]
        if getattr(field, "is_custom_field", False):
            print("Updating Custom Field options...")
            doc = frappe.get_doc("Custom Field", {"dt": doctype, "fieldname": "payment_status"})
            doc.options = "\\n".join(options)
            doc.save()
            print("Options updated.")
        else:
            print("It's a standard Select field. Ensure valid options.")
    else:
        # Create as Custom Field
        create_custom_field(doctype, {
            "fieldname": "payment_status",
            "label": "Payment Status",
            "fieldtype": "Select",
            "options": "Pending\\nPaid\\nFailed\\nRefunded\\nCancelled",
            "insert_after": "email",
            "hidden": 0,
            "read_only": 1,
            "default": "Pending"
        })
        print(f"Added 'payment_status' field to '{doctype}'.")
        
    frappe.db.commit()
