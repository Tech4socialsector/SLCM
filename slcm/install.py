import json
import os
import frappe


def after_install():
	"""
	Runs once when the app is installed on a fresh site.
	Import workspaces only if they don't already exist so that
	cloud-side workspace customisations are never overwritten.
	"""
	_import_missing_workspaces()


def _import_missing_workspaces():
	fixture_path = os.path.join(
		os.path.dirname(__file__), "fixtures", "workspace.json"
	)
	if not os.path.exists(fixture_path):
		return

	with open(fixture_path, "r") as f:
		workspaces = json.load(f)

	for ws in workspaces:
		name = ws.get("name") or ws.get("title")
		if not name:
			continue
		if frappe.db.exists("Workspace", name):
			continue
		try:
			doc = frappe.get_doc(ws)
			doc.flags.ignore_permissions = True
			doc.flags.ignore_mandatory = True
			doc.insert()
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"install: failed to import Workspace '{name}'")

	frappe.db.commit()
