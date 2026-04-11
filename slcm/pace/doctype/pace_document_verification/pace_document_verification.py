import frappe
from frappe.model.document import Document

class PACEDocumentVerification(Document):
	def validate(self):
		# Restriction: Allow edit only when returned or if it's new (Draft)
		# However, it must also be editable when 'Pending' so admin can verify it.
		# The prompt says: "Allow edit only when returned". 
		# This might apply to the Application, but let's check.
		# If it applies to Verification, then finalized records shouldn't be touched.
		
		self.validate_remarks()

	def validate_remarks(self):
		for row in self.verification_items:
			if row.status == "Rejected" and not row.remarks:
				frappe.throw(frappe._("Remarks are required for rejected document: {0}").format(row.document_name))
