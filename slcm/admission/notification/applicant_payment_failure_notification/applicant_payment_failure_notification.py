import frappe

def get_context(context):
	doc = context.get('doc')
	if not doc:
		return context
	
	# If Payment Request is for an Offer Letter, find the User
	if doc.reference_doctype == "Offer Letter":
		applicant = frappe.db.get_value("Offer Letter", doc.reference_name, "applicant")
		if applicant:
			applicant_email = frappe.db.get_value("Applicant", applicant, "email")
			if applicant_email:
				user_name = frappe.db.get_value("User", {"email": applicant_email}, "name")
				if user_name:
					doc.notification_receiver = user_name
	
	return context
