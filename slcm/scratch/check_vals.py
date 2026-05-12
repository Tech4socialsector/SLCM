import frappe

def check_vals():
    doc = frappe.get_doc("Web Form", "pace-application-form")
    print(f"LR: {doc.login_required}")
    print(f"IS: {doc.is_standard}")
    print(f"ADP: {doc.apply_document_permissions}")
    print(f"Route: {doc.route}")

if __name__ == "__main__":
    check_vals()
