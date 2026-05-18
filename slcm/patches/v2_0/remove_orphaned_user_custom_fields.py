import frappe


def execute():
	"""
	Remove orphaned custom fields on User DocType that reference missing child tables,
	preventing global 500 errors during session user load.
	"""
	fields_to_remove = [
		"User-education",
		"User-work_experience",
		"User-internship",
		"User-certification",
		"User-skill",
		"User-preferred_functions",
		"User-preferred_industries",
	]

	for fieldname in fields_to_remove:
		frappe.db.sql("DELETE FROM `tabCustom Field` WHERE name = %s", fieldname)

	# Dynamically remove any Table/Table MultiSelect custom fields on User whose options (child DocType) don't exist
	orphaned = frappe.db.sql("""
		SELECT name, options FROM `tabCustom Field`
		WHERE dt = 'User' AND fieldtype IN ('Table', 'Table MultiSelect')
	""", as_dict=True)

	for cf in orphaned:
		child_dt = (cf.get("options") or "").strip()
		if child_dt and not frappe.db.exists("DocType", child_dt):
			frappe.db.sql("DELETE FROM `tabCustom Field` WHERE name = %s", cf["name"])

	frappe.clear_cache(doctype="User")
