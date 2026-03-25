import frappe

no_cache = True


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/fle/login"
		raise frappe.Redirect

	# frappe.session.user IS the email for website users
	email = frappe.session.user

	doc = frappe.db.get_value(
		"Foundations for a Legal Education",
		{"email_address": email, "payment_status": ["in", ["Authorized", "Paid", "Captured"]]},
		["name", "candidate_name"],
		as_dict=True,
	)

	if not doc:
		# No paid application — send back to the form
		frappe.local.flags.redirect_location = "/foundations-for-a-legal-education/new"
		raise frappe.Redirect

	context.docname = doc.name
	context.candidate_name = doc.candidate_name or ""
