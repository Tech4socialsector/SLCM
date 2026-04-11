import frappe
from frappe.model.document import Document

class PACEReceipt(Document):
	def after_insert(self):
		self.generate_receipt_pdf()

	def generate_receipt_pdf(self):
		"""
		Generates a PDF of the receipt and attaches it to the 'receipt' field.
		Uses the template linked in the Fee Structure if available.
		"""
		try:
			# 1. Navigate to the linked template in PACE Fee Structure
			print_format = "Standard"
			if self.fee_assignment:
				fee_structure = frappe.db.get_value("PACE Applicant Fee Assignment", self.fee_assignment, "fee_structure")
				if fee_structure:
					custom_template = frappe.db.get_value("PACE Fee Structure", fee_structure, "payment_reciept_template")
					if custom_template:
						print_format = custom_template

			# 2. Generate PDF content
			pdf_content = frappe.get_print(self.doctype, self.name, print_format, as_pdf=True)
			filename = f"Receipt_{self.name.replace('-', '_')}.pdf"
			
			# 3. Create a File document
			_file = frappe.get_doc({
				"doctype": "File",
				"file_name": filename,
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
				"content": pdf_content,
				"is_private": 1
			})
			_file.save(ignore_permissions=True)
			
			# 4. Update the receipt field on the current document
			self.db_set("receipt", _file.file_url)
			
		except Exception:
			frappe.log_error(frappe.get_traceback(), "PACE Receipt PDF Generation Failed")

