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

	_ensure_day_of_week()
	clear_grid_customizations()


def clear_grid_customizations():
	"""Clears outdated user settings/customizations to force reload defaults from JSON schema"""
	try:
		doctypes = ["Seat Allocation", "Merit List", "Shortlisting Merit List"]
		for dt in doctypes:
			frappe.db.sql("DELETE FROM `__UserSettings` WHERE `doctype` = %s", dt)
			
			# Clear Redis cache for these user settings
			keys = frappe.cache.hkeys("_user_settings")
			for key in keys:
				key_str = frappe.safe_decode(key)
				if key_str.startswith(f"{dt}::"):
					frappe.cache.hdel("_user_settings", key)
					
		frappe.db.commit()
	except Exception:
		pass


def _ensure_day_of_week():
	"""Ensure Day of Week master doctype and its 7 records exist after every migrate."""
	try:
		if not frappe.db.exists("DocType", "Day of Week"):
			frappe.reload_doc("slcm", "doctype", "day_of_week", force=True)
			frappe.db.commit()

		days = [
			("Monday", 1), ("Tuesday", 2), ("Wednesday", 3), ("Thursday", 4),
			("Friday", 5), ("Saturday", 6), ("Sunday", 7),
		]
		for day_name, day_order in days:
			if not frappe.db.exists("Day of Week", day_name):
				frappe.db.sql(
					"""INSERT INTO `tabDay of Week`
					   (name, day_name, day_order, creation, modified, modified_by, owner, docstatus)
					   VALUES (%s, %s, %s, NOW(), NOW(), 'Administrator', 'Administrator', 0)""",
					(day_name, day_name, day_order),
				)
		frappe.db.commit()
	except Exception:
		pass
