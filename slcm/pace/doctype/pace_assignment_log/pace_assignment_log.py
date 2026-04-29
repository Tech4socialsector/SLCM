import frappe
from frappe.model.document import Document

class PACEAssignmentLog(Document):
	pass

def create_assignment_log(verification_doc, from_verifier, to_verifier, reason=None):
	"""
	Utility function to create a new assignment log entry.
	"""
	log = frappe.get_doc({
		"doctype": "PACE Assignment Log",
		"verification_record": verification_doc.name,
		"application": verification_doc.application,
		"from_verifier": from_verifier,
		"to_verifier": to_verifier,
		"reassigned_by": frappe.session.user,
		"reassignment_date": frappe.utils.now_datetime(),
		"reason": reason
	})
	log.insert(ignore_permissions=True)
	return log
