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

	frappe.clear_cache(doctype="User")
