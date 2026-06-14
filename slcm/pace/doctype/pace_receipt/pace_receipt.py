import io
import json
import os
import zipfile
from typing import Any, Optional, cast

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import format_datetime, now_datetime
from frappe.utils.file_manager import save_file


def get_receipt_template(fee_type, program, academic_year, fee_assignment=None) -> str:
	"""
	Resolve print format template for a PACE Receipt.
	"""
	if fee_type == "Course Fee":
		fs = None
		if fee_assignment:
			fs = frappe.db.get_value("PACE Applicant Fee Assignment", fee_assignment, "fee_structure")
		if not fs and program and academic_year:
			fs = frappe.db.get_value(
				"PACE Fee Structure",
				{"pace_program": program, "academic_year": academic_year, "status": "Active"},
				"name"
			)
		if fs:
			tpl = frappe.db.get_value("PACE Fee Structure", fs, "payment_reciept_template")
			if tpl:
				return tpl
	elif fee_type == "Application Fee":
		admission_name = (
			frappe.db.get_value("PACE Admission", {"academic_year": academic_year, "status": "Active"}, "name")
			or frappe.db.get_value("PACE Admission", {"status": "Active"}, "name")
		)
		if admission_name:
			tpl = frappe.db.get_value("PACE Admission", admission_name, "payment_receipt_template")
			if tpl:
				return tpl
				
	return "PACE Payment Reciept"


@frappe.whitelist()
def get_receipt_template_api(receipt_name: str) -> str:
	doc = frappe.get_doc("PACE Receipt", receipt_name)
	return get_receipt_template(
		fee_type=doc.fee_type,
		program=doc.program,
		academic_year=doc.academic_year,
		fee_assignment=doc.fee_assignment
	)


class PACEReceipt(Document):
	def after_insert(self):
		self.generate_receipt_pdf()

	def generate_receipt_pdf(self):
		"""
		Generates a PDF of the receipt and attaches it to the 'receipt' field.
		Uses the template linked in the Fee Structure or Admission if available.
		"""
		try:
			# 1. Resolve template name using helper
			print_format = get_receipt_template(
				fee_type=self.fee_type,
				program=self.program,
				academic_year=self.academic_year,
				fee_assignment=self.fee_assignment
			)

			# 2. Generate PDF content
			docname = cast(str, self.name)
			pdf_content = frappe.get_print(self.doctype, docname, print_format, as_pdf=True)
			filename = f"Receipt_{docname.replace('-', '_')}.pdf"

			# 3. Create a File document
			_file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": filename,
					"attached_to_doctype": self.doctype,
					"attached_to_name": docname,
					"content": pdf_content,
					"is_private": 1,
				}
			)
			_file.save(ignore_permissions=True)

			# 4. Update the receipt field on the current document
			receipt_url = cast(Optional[str], getattr(_file, "file_url", None))
			if receipt_url:
				self.db_set("receipt", receipt_url)
			
		except Exception:
			frappe.log_error(frappe.get_traceback(), "PACE Receipt PDF Generation Failed")

	def has_website_permission(self, ptype, user, verbose=False):
		if not user:
			user = frappe.session.user
		if self.owner == user:
			return True
		if self.pace_application:
			app_owner = frappe.db.get_value("PACE Application", self.pace_application, "owner")
			if app_owner == user:
				return True
		return False



def _pace_receipt_print_format(receipt_row: dict) -> str:
	return get_receipt_template(
		fee_type=receipt_row.get("fee_type"),
		program=receipt_row.get("program"),
		academic_year=receipt_row.get("academic_year"),
		fee_assignment=receipt_row.get("fee_assignment")
	)


def _as_pdf_bytes(raw: Any) -> Optional[bytes]:
	if isinstance(raw, (bytes, bytearray)):
		return bytes(raw)
	if isinstance(raw, memoryview):
		return raw.tobytes()
	return None


def _get_pace_receipt_pdf_content(receipt_row: dict) -> Optional[bytes]:
	"""Return PDF bytes from attached file or regenerate via Print Format."""
	pdf_content: Optional[bytes] = None
	url = receipt_row.get("receipt")
	if url:
		try:
			from frappe.utils.file_manager import get_file_path

			file_path = get_file_path(url)
			if file_path and os.path.exists(file_path):
				with open(file_path, "rb") as f:
					pdf_content = f.read()
		except Exception:
			pdf_content = None

	if not pdf_content:
		name = receipt_row.get("name")
		if not name:
			return None
		pdf_content = _as_pdf_bytes(
			frappe.get_print(
				"PACE Receipt",
				name,
				_pace_receipt_print_format(receipt_row),
				as_pdf=True,
			)
		)
	return pdf_content


def _pace_update_bulk_progress(i, total, success, failure, user, event_name):
	update_step = 100 if total > 1000 else 10
	if (i + 1) % update_step == 0 or i == total - 1:
		frappe.publish_realtime(
			event_name,
			{
				"progress": [(i + 1) * 100 / total],
				"title": _("Preparing PACE receipt bulk download…"),
				"description": _("Processing {0} of {1} records ({2} successful, {3} failed)").format(
					i + 1, total, success, failure
				),
			},
			user=user or frappe.session.user,
		)


def process_bulk_pace_receipts_zip(receipts, user=None, output_format="ZIP Archive"):
	import tempfile

	total = len(receipts)
	success_count = 0
	failure_count = 0
	errors = []

	with tempfile.NamedTemporaryFile(
		delete=False, suffix=".zip" if output_format == "ZIP Archive" else ".pdf"
	) as temp_out:
		temp_path = temp_out.name

		if output_format == "ZIP Archive":
			with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
				for i, rec in enumerate(receipts):
					applicant = (rec.get("applicant_name") or rec.get("pace_application") or rec.get("name") or "").strip()
					pd = rec.get("payment_date")
					formatted = format_datetime(pd, "dd-MM-yyyy HH:mm") if pd else "nodate"
					filename = f"{applicant} - PACE receipt ({formatted}).pdf".replace("/", "-")

					try:
						content = _get_pace_receipt_pdf_content(rec)
						if content:
							zip_file.writestr(filename, content)
							success_count += 1
						else:
							failure_count += 1
							errors.append(f"Empty content for {rec.get('name')}")
					except Exception as e:
						failure_count += 1
						errors.append(f"Error zipping {rec.get('name')}: {e!s}")

					_pace_update_bulk_progress(
						i, total, success_count, failure_count, user, "bulk_pace_receipt_download_progress"
					)
		else:
			try:
				from pypdf import PdfWriter  # type: ignore[import-not-found]
			except ImportError:
				from PyPDF2 import PdfWriter  # type: ignore[import-not-found]

			merger = PdfWriter()
			for i, rec in enumerate(receipts):
				try:
					content = _get_pace_receipt_pdf_content(rec)
					if content:
						merger.append(io.BytesIO(memoryview(content)))
						success_count += 1
					else:
						failure_count += 1
						errors.append(f"Empty content for {rec.get('name')}")
				except Exception as e:
					failure_count += 1
					errors.append(f"Error merging {rec.get('name')}: {e!s}")

				_pace_update_bulk_progress(
					i, total, success_count, failure_count, user, "bulk_pace_receipt_download_progress"
				)

			with open(temp_path, "wb") as f:
				merger.write(f)
			merger.close()

	if success_count == 0:
		if os.path.exists(temp_path):
			os.remove(temp_path)
		frappe.throw(_("Failed to generate any PACE receipts. Please check the error logs."))

	final_name = f"Bulk_PACE_Receipts_{now_datetime().strftime('%Y%m%d_%H%M%S')}"
	final_name += ".zip" if output_format == "ZIP Archive" else ".pdf"

	with open(temp_path, "rb") as f:
		saved_file = save_file(
			final_name,
			f.read(),
			"PACE Receipt",
			"Bulk Download",
			is_private=1,
		)

	if os.path.exists(temp_path):
		os.remove(temp_path)

	summary = _("Bulk download complete: {0} PACE receipt(s)").format(success_count)
	if failure_count > 0:
		summary += _(", {0} failed").format(failure_count)

	bulk_file_url = cast(Optional[str], getattr(saved_file, "file_url", None))
	if not bulk_file_url:
		frappe.throw(_("Could not save bulk download file."))

	return bulk_file_url, summary, errors


@frappe.whitelist()
def get_bulk_pace_receipts_zip(filters):
	if isinstance(filters, str):
		filters = json.loads(filters)

	query_filters = {}
	if filters.get("program"):
		query_filters["program"] = filters["program"]
	if filters.get("fee_type"):
		query_filters["fee_type"] = filters["fee_type"]

	if filters.get("from_date") and filters.get("to_date"):
		query_filters["payment_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		query_filters["payment_date"] = [">=", filters["from_date"]]
	elif filters.get("to_date"):
		query_filters["payment_date"] = ["<=", filters["to_date"]]

	output_format = filters.get("output_format", "ZIP Archive")

	receipts = frappe.get_all(
		"PACE Receipt",
		filters=query_filters,
		fields=["name", "pace_application", "applicant_name", "payment_date", "receipt", "fee_assignment"],
	)

	if not receipts:
		frappe.throw(_("No PACE receipts found for the selected filters."))

	if len(receipts) > 10:
		frappe.enqueue(
			method="slcm.pace.doctype.pace_receipt.pace_receipt.bulk_pace_receipts_zip_worker",
			queue="long",
			receipts=receipts,
			user=frappe.session.user,
			output_format=output_format,
		)
		return {
			"status": "enqueued",
			"message": _("Preparing {0} for {1} PACE receipt(s) in the background. You will be notified when it is ready.").format(
				output_format, len(receipts)
			),
		}

	file_url, _summary, _errors = process_bulk_pace_receipts_zip(
		receipts, user=frappe.session.user, output_format=output_format
	)
	return file_url


@frappe.whitelist()
def bulk_pace_receipts_zip_worker(receipts, user, output_format="ZIP Archive"):
	frappe.set_user(user)
	try:
		file_url, summary, errors = process_bulk_pace_receipts_zip(
			receipts, user=user, output_format=output_format
		)

		error_details = ""
		if errors:
			error_details = "<br><br><b>Errors:</b><ul>" + "".join(f"<li>{e}</li>" for e in errors[:10]) + "</ul>"
			if len(errors) > 10:
				error_details += _("<p>...and {0} more errors.</p>").format(len(errors) - 10)

		from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

		enqueue_create_notification(
			[user],
			{
				"subject": _("PACE receipt bulk download ready"),
				"email_content": _("{0}. <a href='{1}' target='_blank'><b>Click here to download</b></a>. {2}").format(
					summary, file_url, error_details
				),
				"type": "Alert",
				"document_type": "PACE Receipt",
			},
		)

		frappe.publish_realtime(
			"bulk_download_complete",
			{"file_url": file_url, "doctype": "PACE Receipt"},
			user=user,
		)
	except Exception as e:
		frappe.log_error(f"Bulk PACE receipt download failed: {e!s}", "Bulk PACE Receipt Download")
