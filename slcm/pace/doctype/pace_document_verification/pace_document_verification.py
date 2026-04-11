import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import get_url
import traceback

class PACEDocumentVerification(Document):
	def validate(self):
		self.validate_remarks()

	def validate_remarks(self):
		for row in self.verification_items:
			if row.status == "Rejected" and not row.remarks:
				frappe.throw(frappe._("Remarks are required for rejected document: {0}").format(row.document_name))

	def on_update(self):
		"""
		Trigger summary notification when status changes or when forced (Finalize button).
		"""
		doc_before_save = self.get_doc_before_save()
		old_overall_status = doc_before_save.overall_status if doc_before_save else "Pending"
		
		# Trigger conditions:
		# 1. Status changed to a final state (Verified/Returned)
		# 2. Or the 'force_notification' flag is set (from the Finalize button)
		is_final_status = self.overall_status in ["Verified", "Returned for Correction"]
		status_changed = self.overall_status != old_overall_status
		
		if is_final_status and (status_changed or self.flags.force_notification):
			self.send_final_verification_notification()

	def send_final_verification_notification(self):
		"""
		Sends a comprehensive summary email and system notification.
		"""
		try:
			template_name = "PACE Document Verification Final Update"
			
			# 1. Check if Applicant Email exists
			recipient = frappe.db.get_value("PACE Application", self.application, "email_address")
			if not recipient:
				frappe.msgprint(_("Warning: No email address found for the applicant. Email not sent."), indicator='orange', alert=True)
				return

			# 2. Check if Template exists
			if not frappe.db.exists("Email Template", template_name):
				frappe.msgprint(_("Error: Email Template '{0}' not found. Please create it to send notifications.").format(template_name), indicator='red', alert=True)
				return

			email_template = frappe.get_doc("Email Template", template_name)
			
			# Prepare Args
			inst_settings = frappe.get_single("Institution Settings")
			args = {
				"doc": self,
				"admission_portal_url": get_url("/admissions"),
				"institution_name": inst_settings.institution_name
			}

			# Render Content
			subject = frappe.render_template(email_template.subject, args)
			
			if email_template.get("use_html"):
				message = frappe.render_template(email_template.response_html, args)
			else:
				message = frappe.render_template(email_template.response, args)

			if not message:
				message = frappe.render_template(email_template.get("message") or "", args)

			# CC handling
			cc_list = []
			cc_field_value = email_template.get("cc")
			if cc_field_value:
				cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]

			# 3. Send Email
			frappe.sendmail(
				recipients=[recipient],
				cc=cc_list,
				subject=subject,
				content=message,
				reference_doctype=self.doctype,
				reference_name=self.name,
				now=True
			)

			# 4. Create System Notification
			if frappe.db.exists("User", recipient):
				frappe.get_doc({
					"doctype": "Notification Log",
					"subject": f"Document Verification Update: {self.overall_status}",
					"for_user": recipient,
					"type": "Alert",
					"email_content": message,
					"document_type": self.doctype,
					"document_name": self.name,
					"from_user": frappe.session.user or "Administrator",
					"link": "/admissions"
				}).insert(ignore_permissions=True)

			# 5. Show Success Toast
			frappe.msgprint(_("Verification summary email successfully triggered to {0}").format(recipient), indicator='green', alert=True)

		except Exception:
			frappe.log_error(traceback.format_exc(), f"PACE Verification Final Notification Failed: {self.name}")
			frappe.msgprint(_("Critical: Failed to trigger notification. Check Error Logs."), indicator='red', alert=True)
