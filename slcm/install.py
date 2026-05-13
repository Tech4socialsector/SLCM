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
	pass
