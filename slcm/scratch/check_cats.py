import frappe

def check_categories():
    cats = frappe.get_all("Admission Category", fields=["name", "reservation_type"])
    for c in cats:
        print(f"Name: {c.name}, Type: {c.reservation_type}")

if __name__ == "__main__":
    frappe.init(site="127.0.0.1")
    frappe.connect()
    check_categories()
