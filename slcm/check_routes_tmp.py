import frappe
def check_routes():
    print(frappe.get_hooks('website_route_rules'))

if __name__ == "__main__":
    check_routes()
