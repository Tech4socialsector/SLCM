import frappe


def execute():
	name = "applicant-form"
	if not frappe.db.exists("Web Form", name):
		return
	bc = frappe.db.get_value("Web Form", name, "breadcrumbs") or ""
	if "list as" not in bc.lower():
		return
	fixed = '[{"label": _("Back"), "route": "admission"}]'
	frappe.db.set_value("Web Form", name, "breadcrumbs", fixed)
