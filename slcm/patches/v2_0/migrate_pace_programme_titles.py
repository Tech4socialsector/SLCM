import frappe


def execute():
	"""Migrate existing PACE Programme records to set the title field and rename them accordingly."""
	if not frappe.db.exists("DocType", "PACE Programme"):
		return
	if not frappe.db.has_column("PACE Programme", "title"):
		return

	programmes = frappe.get_all("PACE Programme", fields=["name", "programme_prefix", "programme_name"])
	for p in programmes:
		prefix = (p.programme_prefix or "").strip()
		name = (p.programme_name or "").strip()
		new_title = f"{prefix} {name}".strip()
		if new_title:
			# Update title in the DB first
			frappe.db.set_value("PACE Programme", p.name, "title", new_title)
			# Rename the document if the name is not already the new title
			if p.name != new_title:
				try:
					frappe.rename_doc("PACE Programme", p.name, new_title, force=True)
				except Exception as e:
					frappe.log_error(
						title="PACE Programme Rename Migration Failed",
						message=f"Failed to rename PACE Programme '{p.name}' to '{new_title}': {str(e)}"
					)
