import frappe
from frappe.model.document import Document

class PACEDocumentVerification(Document):
	def validate(self):
		self.validate_remarks()



	def validate_remarks(self):
		for row in self.verification_items:
			if row.status in ["Rejected", "Returned for Correction"] and not row.remarks:
				frappe.throw(frappe._("Remarks are required for {0} (field: {1}) because it is {2}.").format(
					row.document_name, row.fieldname, row.status
				))


