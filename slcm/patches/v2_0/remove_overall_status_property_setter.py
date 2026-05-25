import frappe

def execute():
	# 1. Delete property setters referencing overall_status on PACE Document Verification
	property_setters = frappe.get_all(
		"Property Setter",
		filters={"doc_type": "PACE Document Verification", "field_name": "overall_status"},
		fields=["name"]
	)
	for ps in property_setters:
		frappe.delete_doc("Property Setter", ps.name, ignore_permissions=True, force=True)
		frappe.logger().info(f"[slcm] Deleted PACE Document Verification Property Setter: {ps.name}")

	# 2. Also delete any Custom Fields referencing overall_status on PACE Document Verification
	custom_fields = frappe.get_all(
		"Custom Field",
		filters={"dt": "PACE Document Verification", "fieldname": "overall_status"},
		fields=["name"]
	)
	for cf in custom_fields:
		frappe.delete_doc("Custom Field", cf.name, ignore_permissions=True, force=True)
		frappe.logger().info(f"[slcm] Deleted PACE Document Verification Custom Field: {cf.name}")

	frappe.db.commit()
