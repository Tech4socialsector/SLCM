import frappe

def execute():
	"""
	Ensure Applicant Form stays Desk-editable (is_standard = 0).
	Module JS/CSS is still injected on the portal via portal_application_web_form logic.
	"""
	name = "applicant-form"
	if not frappe.db.exists("Web Form", name):
		return
	if frappe.db.get_value("Web Form", name, "is_standard"):
		frappe.db.set_value("Web Form", name, "is_standard", 0)
		frappe.db.commit()
