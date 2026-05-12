import frappe


def generate_id_card_images(docname):
	try:
		doc = frappe.get_doc("ID Card Generation", docname)
		doc.generate_card()
	except Exception as e:
		frappe.log_error(f"ID Card Generation Failed for {docname}: {e!s}", "ID Card Generation Error")
		frappe.db.set_value("ID Card Generation", docname, "card_status", "Error")
		frappe.db.commit()
