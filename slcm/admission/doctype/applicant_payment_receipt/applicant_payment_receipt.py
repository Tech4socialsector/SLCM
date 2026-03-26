import io
import json
import zipfile

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import formatdate, now_datetime
from frappe.utils.file_manager import save_file


class ApplicantPaymentReceipt(Document):
	def validate(self):
		self.set_notification_receiver()

	def set_notification_receiver(self):
		if self.applicant:
			applicant_email = frappe.db.get_value("Applicant", self.applicant, "email")
			if applicant_email:
				user_name = frappe.db.get_value("User", {"email": applicant_email}, "name")
				if user_name:
					self.notification_receiver = user_name


@frappe.whitelist()
def get_bulk_receipts_zip(filters):
	if isinstance(filters, str):
		filters = json.loads(filters)

	query_filters = {}
	if filters.get("program"):
		query_filters["program"] = filters["program"]
	if filters.get("academic_year"):
		query_filters["academic_year"] = filters["academic_year"]
	if filters.get("payment_mode"):
		query_filters["payment_mode"] = filters["payment_mode"]

	if filters.get("from_date") and filters.get("to_date"):
		query_filters["payment_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		query_filters["payment_date"] = [">=", filters["from_date"]]
	elif filters.get("to_date"):
		query_filters["payment_date"] = ["<=", filters["to_date"]]

	receipts = frappe.get_all(
		"Applicant Payment Receipt",
		filters=query_filters,
		fields=["name", "applicant", "payment_date"],
	)

	if not receipts:
		frappe.throw(_("No receipts found for the selected filters."))

	if len(receipts) > 10:
		frappe.enqueue(
			method="slcm.admission.doctype.applicant_payment_receipt.applicant_payment_receipt.bulk_receipts_zip_worker",
			queue="long",
			receipts=receipts,
			user=frappe.session.user
		)
		return {
			"status": "enqueued",
			"message": _("Preparing ZIP for {0} fee receipts in the background. You will receive a notification when it's ready.").format(len(receipts))
		}

	return process_bulk_receipts_zip(receipts, user=frappe.session.user)

@frappe.whitelist()
def bulk_receipts_zip_worker(receipts, user):
	frappe.set_user(user)
	try:
		file_url = process_bulk_receipts_zip(receipts, user=user)
		
		from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
		enqueue_create_notification(
			[user],
			{
				"subject": _("Bulk Receipt Download Ready"),
				"email_content": _("Your ZIP archive for {0} receipts is ready. <a href='{1}' target='_blank'><b>Click here to download</b></a>.").format(len(receipts), file_url),
				"type": "Alert",
				"document_type": "Applicant Payment Receipt"
			}
		)

		# AUTO-DOWNLOAD TRIGGER
		frappe.publish_realtime("bulk_download_complete", {
			"file_url": file_url,
			"doctype": "Applicant Payment Receipt"
		}, user=user)

	except Exception as e:
		frappe.log_error(f"Bulk Receipt Download Worker Failed: {e!s}", "Bulk Download Error")

def process_bulk_receipts_zip(receipts, user=None):
	from frappe.utils import formatdate
	zip_buffer = io.BytesIO()
	total = len(receipts)
	# The specific filename format requested:
	# APP-2026-00069 - fee recept ( 26-03-2026 ) .pdf
	with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
		for i, receipt in enumerate(receipts):
			formatted_date = formatdate(receipt.payment_date, "dd-mm-yyyy")
			filename = f"{receipt.applicant} - fee receipt ( {formatted_date} ).pdf"

			try:
				pdf_content = frappe.get_print(
					"Applicant Payment Receipt",
					receipt.name,
					"Applicant Payment Receipt Format",
					as_pdf=True,
				)
				zip_file.writestr(filename, pdf_content)
			except Exception as e:
				frappe.log_error(f"Error generating PDF for {receipt.name}: {e!s}", "Bulk Receipt Download Error")
				continue
			
			# Real-time progress update
			if (i + 1) % 5 == 0 or i == total - 1:
				frappe.publish_realtime("bulk_receipt_download_progress", {
					"progress": [(i + 1) * 100 / total],
					"title": _("Preparing Bulk Download..."),
					"description": _("Processing {0} of {1} fee receipts").format(i + 1, total)
				}, user=user or frappe.session.user)

	zip_filename = f"Bulk_Fee_Receipts_{now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"
	saved_zip = save_file(
		zip_filename,
		zip_buffer.getvalue(),
		"Applicant Payment Receipt",
		"Bulk Download",
		is_private=1,
	)

	return saved_zip.file_url
