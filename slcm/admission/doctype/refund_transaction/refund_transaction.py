import frappe
import json
import os
import zipfile
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, get_files_path
from frappe.utils.pdf import get_pdf
from io import BytesIO

class RefundTransaction(Document):
	def validate(self):
		self.fetch_request_details()

	def fetch_request_details(self):
		if self.refund_request and not self.razorpay_payment_id:
			request = frappe.get_doc("Refund Request", self.refund_request)
			self.payment_request = request.payment_request
			self.razorpay_payment_id = request.razorpay_payment_id
			self.refund_amount = flt(request.refund_amount)

@frappe.whitelist()
def bulk_download_receipts_by_filter(admission_cycle, status=None):
	filters = {}
	if status:
		filters["status"] = status
	
	# We need to filter Refund Transactions where the linked Refund Request's 
	# Applicant belongs to the specified Admission Cycle.
	
	sql_query = """
		SELECT 
			rt.name 
		FROM 
			`tabRefund Transaction` rt
		JOIN 
			`tabRefund Request` rr ON rt.refund_request = rr.name
		JOIN 
			`tabApplicant` app ON rr.applicant = app.name
		WHERE 
			app.admission_cycle = %(admission_cycle)s
	"""
	
	if status:
		sql_query += " AND rt.status = %(status)s"
		
	names_data = frappe.db.sql(sql_query, {"admission_cycle": admission_cycle, "status": status}, as_dict=True)
	names = [d.name for d in names_data]
	
	if not names:
		return None

	return bulk_download_receipts(names)

@frappe.whitelist()
def bulk_download_receipts(names):
	if isinstance(names, str):
		names = json.loads(names)

	if not names:
		frappe.throw(_("No records selected for download."))

	zip_buffer = BytesIO()
	files_added = 0
	
	with zipfile.ZipFile(zip_buffer, "w") as zip_file:
		for name in names:
			try:
				txn = frappe.get_doc("Refund Transaction", name)
				if txn.refund_request:
					# Generate PDF for Refund Request
					pdf_content = get_pdf_for_refund_request(txn.refund_request)
					if pdf_content:
						filename = f"Receipt_{txn.refund_request}_{name}.pdf"
						zip_file.writestr(filename, pdf_content)
						files_added += 1
					else:
						frappe.logger().warning(f"Bulk Receipt Download: PDF generation returned empty for {txn.refund_request}")
				else:
					frappe.logger().warning(f"Bulk Receipt Download: No Refund Request linked to Transaction {name}")
			except Exception as e:
				frappe.logger().error(f"Bulk Receipt Download: Failed to process {name}: {str(e)}")

	if files_added == 0:
		return None

	zip_buffer.seek(0)
	
	file_name = f"Refund_Receipts_{now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"
	
	# Save to private files
	file_doc = frappe.get_doc({
		"doctype": "File",
		"file_name": file_name,
		"content": zip_buffer.getvalue(),
		"is_private": 1
	})
	file_doc.insert(ignore_permissions=True)
	
	return {
		"file_url": file_doc.file_url,
		"file_name": file_name,
		"count": files_added
	}

def get_pdf_for_refund_request(refund_request_name):
	try:
		# frappe.get_print returns the PDF content as bytes when as_pdf=True
		pdf_content = frappe.get_print("Refund Request", refund_request_name, "Refund Receipt Format", as_pdf=True)
		return pdf_content
	except Exception as e:
		frappe.log_error(f"Error generating PDF for {refund_request_name}: {str(e)}", "Bulk Receipt Download")
		return None
