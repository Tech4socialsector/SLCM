import frappe

def get_context(context):
	# The context is already populated with 'doc' (the Offer Letter).
	doc = context.get('doc')
	if not doc:
		return context
	
	# Fetch the User ID from the linked Applicant's email 
	# System Notifications requirement: the receiver must be a User ID
	if doc.applicant:
		applicant_email = frappe.db.get_value("Applicant", doc.applicant, "email")
		if applicant_email:
			# Find the User record associated with this email
			user_name = frappe.db.get_value("User", {"email": applicant_email}, "name")
			if user_name:
				# Use a fieldname that matches the 'receiver_by_document_field' in notification JSON
				doc.notification_receiver = user_name
			
	# Ensure applicant name is available for the template
	if doc.applicant and not getattr(doc, 'applicant_name', None):
		doc.applicant_name = frappe.db.get_value("Applicant", doc.applicant, "candidate_name")
	
	return context
