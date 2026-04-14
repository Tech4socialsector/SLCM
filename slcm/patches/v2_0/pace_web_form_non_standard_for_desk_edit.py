import frappe


def execute():
	"""
	Match Application Form behaviour: PACE Web Form stays Desk-editable (is_standard = 0).
	Module JS/CSS is injected on the portal via portal_application_web_form patch.
	"""
	name = "pace-application-form"
	if not frappe.db.exists("Web Form", name):
		return
	if frappe.db.get_value("Web Form", name, "is_standard"):
		frappe.db.set_value("Web Form", name, "is_standard", 0)
