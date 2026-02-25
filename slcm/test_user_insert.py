import frappe

def run():
    doc = frappe.get_doc({
        "doctype": "User",
        "email": "test_insert2@example.com",
        "first_name": "Test",
        "enabled": 1,
        "send_welcome_email": 0
    })
    try:
        doc.insert(ignore_permissions=True)
        print("Success")
    except Exception as e:
        print("Error:", str(e))
        print(frappe.get_traceback())
