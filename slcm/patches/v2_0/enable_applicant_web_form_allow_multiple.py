import frappe


def execute():
	"""Multiple programme applications per user require allow_multiple on the Applicant web form.

	Frappe otherwise redirects /applicant-form/new to the first Applicant owned by the user
	(WebForm.get_context and get_form_data), showing the wrong programme.
	"""
	name = "applicant-form"
	if not frappe.db.exists("Web Form", name):
		return
	if frappe.db.get_value("Web Form", name, "allow_multiple"):
		return
	frappe.db.set_value("Web Form", name, "allow_multiple", 1)
