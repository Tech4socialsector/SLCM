from frappe.utils.fixtures import sync_fixtures


def after_install():
	"""
	Runs once when the app is installed on a fresh site.
	Syncs all fixtures (workspaces, desktop icons, workspace sidebars, etc.)
	so the desk is fully configured on a fresh Frappe Cloud deployment.
	"""
	sync_fixtures(app="slcm")
