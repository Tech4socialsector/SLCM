import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def add_gateway_response_field():
    custom_fields = {
        "FLE Payment Log": [
            {
                "fieldname": "gateway_response",
                "label": "Gateway Response",
                "fieldtype": "Code",
                "options": "JSON",
                "insert_after": "transaction_date",
                "read_only": 1
            }
        ]
    }
    create_custom_fields(custom_fields)
    print("Added gateway_response field to FLE Payment Log successfully.")

add_gateway_response_field()
