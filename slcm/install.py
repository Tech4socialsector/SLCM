import frappe

def after_install():
	"""
	Runs once when the app is installed on a fresh site.

	Workspaces, Desktop Icons and Workspace Sidebars are loaded automatically
	by Frappe's model sync (sync_for) before this hook fires, so no manual
	import is needed here.

	Fixtures (roles, number cards, etc.) are loaded by Frappe's own
	sync_fixtures call that runs immediately after after_install, so we do
	not call it ourselves to avoid a redundant double-import.
	"""
	from slcm.slcm.student_portal.sp_fee_reminders import seed_email_templates
	seed_email_templates()


def after_migrate():
	"""
	Runs after every bench migrate.
	Cleans up orphaned custom fields on the User DocType to prevent site-wide 500 errors.
	"""
	try:
		# 1. Remove specifically known orphaned fields if present
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

		# 2. Dynamically remove any Table/Table MultiSelect custom fields on User whose options (child DocType) don't exist
		orphaned = frappe.db.sql("""
			SELECT name, options FROM `tabCustom Field`
			WHERE dt = 'User' AND fieldtype IN ('Table', 'Table MultiSelect')
		""", as_dict=True)

		removed_any = False
		for cf in orphaned:
			child_dt = (cf.get("options") or "").strip()
			if child_dt and not frappe.db.exists("DocType", child_dt):
				frappe.db.sql("DELETE FROM `tabCustom Field` WHERE name = %s", cf["name"])
				removed_any = True

		frappe.clear_cache(doctype="User")
	except Exception:
		pass

	from slcm.slcm.student_portal.sp_fee_reminders import seed_email_templates
	seed_email_templates()
