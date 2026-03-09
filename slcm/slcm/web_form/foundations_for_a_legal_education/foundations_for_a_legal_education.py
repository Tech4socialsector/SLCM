import frappe

def get_context(context):
	# Disable the default header and footer
	context.no_header = 1
	context.no_footer = 1

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/fle/login.html"
		raise frappe.Redirect
