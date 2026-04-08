import frappe
import json
import re
import zipfile
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime
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
	"""
	Called from the frontend.
	Runs a quick SQL query to find matching records, then enqueues the
	heavy PDF-generation work so the HTTP response returns immediately.
	"""
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

	params = {"admission_cycle": admission_cycle, "status": status}

	if status:
		sql_query += " AND rt.status = %(status)s"

	names_data = frappe.db.sql(sql_query, params, as_dict=True)
	names = [d.name for d in names_data]

	if not names:
		# Return a special status so the frontend can show the right message
		return {"status": "NoRecords"}

	# Enqueue the heavy work — this returns immediately, no UI freeze
	frappe.enqueue(
		"slcm.admission.doctype.refund_transaction.refund_transaction.bulk_download_worker",
		queue="long",
		timeout=1800,
		names=names,
		user=frappe.session.user,
		now=frappe.flags.in_test,  # runs synchronously only during unit tests
	)

	return {"status": "Started", "count": len(names)}


# ── Background worker ─────────────────────────────────────────────────────────

def bulk_download_worker(names, user=None):
	"""
	Runs inside a background Frappe worker (Redis queue).
	Generates PDFs, zips them, saves to private files, then notifies
	the browser via realtime so it can auto-download.
	"""
	if not names:
		return

	if user:
		frappe.set_user(user)

	total = len(names)
	zip_buffer = BytesIO()
	files_added = 0

	with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
		for i, name in enumerate(names):
			# ── Publish live progress ──────────────────────────────────
			frappe.publish_realtime(
				"bulk_download_progress",
				{
					"progress": i + 1,
					"total": total,
					"message": _("Generating receipt {0} of {1}: {2}").format(i + 1, total, name),
					"doctype": "Refund Transaction",
				},
				user=user,
			)

			try:
				txn = frappe.get_doc("Refund Transaction", name)
				if not txn.refund_request:
					frappe.logger().warning(
						f"Bulk Receipt Download: No Refund Request linked to Transaction {name}"
					)
					continue

				pdf_content = get_pdf_for_refund_request(txn.refund_request)
				if pdf_content:
					filename = f"Receipt_{txn.refund_request}_{name}.pdf"
					zip_file.writestr(filename, pdf_content)
					files_added += 1
				else:
					frappe.logger().warning(
						f"Bulk Receipt Download: PDF generation returned empty for {txn.refund_request}"
					)

			except Exception as e:
				frappe.logger().error(
					f"Bulk Receipt Download: Failed to process {name}: {str(e)}"
				)

	# ── Publish final result ───────────────────────────────────────────────
	if files_added == 0:
		frappe.publish_realtime(
			"bulk_download_complete",
			{
				"error": _("Failed to generate any receipts. Check error logs for details."),
				"doctype": "Refund Transaction",
			},
			user=user,
		)
		return

	zip_buffer.seek(0)
	file_name = f"Refund_Receipts_{now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"

	# Save the zip to Frappe private files
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": file_name,
			"content": zip_buffer.getvalue(),
			"is_private": 1,
		}
	)
	file_doc.insert(ignore_permissions=True)

	frappe.publish_realtime(
		"bulk_download_complete",
		{
			"file_url": file_doc.file_url,
			"file_name": file_name,
			"count": files_added,
			"doctype": "Refund Transaction",
		},
		user=user,
	)


# ── PDF helper ────────────────────────────────────────────────────────────────

def _rewrite_urls_for_worker(html, port):
	"""
	wkhtmltopdf runs inside a background worker that cannot resolve the
	site hostname (e.g. v16.local → HostNotFoundError).

	This function rewrites every URL in the HTML so all requests go to
	http://127.0.0.1:<port> (the local gunicorn process) instead:

	  • Absolute site URL  http://v16.local/assets/... → http://127.0.0.1:<port>/assets/...
	  • Bare absolute path /assets/frappe/css/x.css    → http://127.0.0.1:<port>/assets/...
	  • url('/assets/...')  in inline styles            → url('http://127.0.0.1:<port>/assets/...')
	"""
	local_base = f"http://127.0.0.1:{port}"

	# 1. Replace the configured site URL (handles http:// and https://)
	site_url = frappe.utils.get_url().rstrip("/")
	html = html.replace(site_url, local_base)

	# 2. Rewrite href="/..." and src="/..." (bare absolute paths)
	html = re.sub(
		r'(href|src)=(["\'])(/[^"\'>\s]+)\2',
		lambda m: f'{m.group(1)}={m.group(2)}{local_base}{m.group(3)}{m.group(2)}',
		html,
	)

	# 3. Rewrite url('/...') or url("/...") in inline styles
	html = re.sub(
		r'url\((["\']?)(/[^"\')\s]+)\1\)',
		lambda m: f'url({m.group(1)}{local_base}{m.group(2)}{m.group(1)})',
		html,
	)

	return html


def get_pdf_for_refund_request(refund_request_name):
	"""
	Renders the Refund Receipt print format to PDF.
	Safe to call from a background worker (no DNS lookups needed).
	"""
	try:
		from frappe.utils.pdf import get_pdf

		# Step 1 – render Jinja template → raw HTML  (no HTTP request)
		html = frappe.get_print(
			"Refund Request",
			refund_request_name,
			"Refund Receipt Format",
		)

		# Step 2 – patch all URLs so wkhtmltopdf uses 127.0.0.1
		port = frappe.conf.get("webserver_port", 8000)
		html = _rewrite_urls_for_worker(html, port)

		# Step 3 – convert HTML → PDF with graceful error handling
		pdf_options = {
			"load-error-handling":       "ignore",
			"load-media-error-handling": "ignore",
			"disable-javascript":        "",
			"no-stop-slow-scripts":      "",
			"quiet":                     "",
		}

		pdf_content = get_pdf(html, pdf_options)
		return pdf_content

	except Exception as e:
		frappe.log_error(
			f"Error generating PDF for {refund_request_name}: {str(e)}",
			"Bulk Receipt Download",
		)
		return None
