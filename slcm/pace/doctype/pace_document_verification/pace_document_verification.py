import frappe
from frappe.model.document import Document

class PACEDocumentVerification(Document):
	def validate(self):
		self.validate_remarks()

	def validate_remarks(self):
		for row in self.verification_items:
			if row.status == "Rejected" and not row.remarks:
				frappe.throw(frappe._("Remarks are required for rejected document: {0}").format(row.document_name))

def get_permission_query_conditions(user=None):
	if not user:
		user = frappe.session.user

	# Absolute bypass for the master Administrator user
	if user == "Administrator":
		return ""

	roles = frappe.get_roles(user)
	
	# If they are a Document Verifier, force the restriction
	if "Document Verifier" in roles:
		return f"assigned_verifier = {frappe.db.escape(user)}"

	# For other administrative roles (System Manager/Academic Manager), see everything
	if "System Manager" in roles or "Academic Manager" in roles:
		return ""

	# Default: Restrict to assigned verifier
	return f"assigned_verifier = {frappe.db.escape(user)}"

def has_permission(doc, ptype, user):
	if "System Manager" in frappe.get_roles(user) or "Academic Manager" in frappe.get_roles(user):
		return True
	
	if doc.assigned_verifier == user:
		return True
	
	return False
