import frappe
providers = frappe.get_all("Entrance Test Provider", fields=["name", "center_name", "campus", "active"])
print(providers)
