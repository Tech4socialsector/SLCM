import frappe


def execute():
	"""Draft applications must open in edit mode; allow_edit was off in some DB copies."""
	name = "applicant-form"
	if not frappe.db.exists("Web Form", name):
		return
	if frappe.db.get_value("Web Form", name, "allow_edit"):
		return
	frappe.db.set_value("Web Form", name, "allow_edit", 1)
