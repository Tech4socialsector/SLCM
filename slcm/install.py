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
	sync_pace_number_cards()


def sync_pace_number_cards():
	"""
	Ensures PACE Number Cards are synced with proper document types and standard SQL query mode.
	Runs on every bench migrate so all team members automatically get correct cards without manual DB fixes.
	"""
	try:
		# 1. Reset any old custom method overrides on PACE Number Cards
		frappe.db.sql("""
			UPDATE `tabNumber Card`
			SET type = 'Document Type', method = NULL
			WHERE module = 'PACE' AND (method LIKE '%pace_admin_dashboard%' OR method IS NOT NULL)
		""")

		# 2. Reload all PACE Number Cards from disk with force=True
		pace_cards = [
			"total_applications_received", "draft_applications", "submitted_applications",
			"awaiting_verification", "applications_verified", "fee_paid_applications",
			"students_enrolled", "returned_for_correction", "applications_rejected",
			"withdrawn_application", "application_fees_collected", "course_fees_collected",
			"total_fees_collected"
		]
		for card in pace_cards:
			try:
				frappe.reload_doc("pace", "number_card", card, force=True)
			except Exception:
				pass

		# 3. Direct DB updates for specific doctype mappings
		if frappe.db.exists("Number Card", "Applications Verified"):
			frappe.db.set_value("Number Card", "Applications Verified", {
				"document_type": "PACE Document Verification",
				"filters_json": '[["PACE Document Verification","status","=","Verified"]]'
			}, update_modified=False)

		if frappe.db.exists("Number Card", "Returned For Correction"):
			frappe.db.set_value("Number Card", "Returned For Correction", {
				"document_type": "PACE Document Verification",
				"filters_json": '[["PACE Document Verification","status","=","Returned for Correction"]]'
			}, update_modified=False)

		if frappe.db.exists("Number Card", "Fee Paid Applications"):
			frappe.db.set_value("Number Card", "Fee Paid Applications", {
				"document_type": "PACE Receipt",
				"filters_json": '[]'
			}, update_modified=False)

		frappe.db.commit()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "PACE Number Card Sync Error")


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
