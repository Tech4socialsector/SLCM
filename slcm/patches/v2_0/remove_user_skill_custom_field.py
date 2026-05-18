import frappe


def execute():
	for field_name in ("User-skill", "User-skill_details"):
		if frappe.db.exists("Custom Field", field_name):
			frappe.delete_doc("Custom Field", field_name, ignore_permissions=True, force=True)
			frappe.logger().info(f"[slcm] Deleted Custom Field: {field_name}")

	frappe.db.commit()
