import frappe
logs = frappe.get_all("Error Log",
    filters={"method": "Portal Debug"},
    fields=["error", "creation"],
    order_by="creation desc",
    limit=20)
for l in logs:
    print(f"{l.creation} : {l.error[:300]}")
    print("---")
