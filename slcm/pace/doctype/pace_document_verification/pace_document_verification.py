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

	def before_save(self):
		"""
		Clean up flags when status is changed by verifier.
		"""
		doc_before_save = self.get_doc_before_save()
		if not doc_before_save:
			return

		old_status = doc_before_save.overall_status
		
		# If verifier changes status to "Returned for Correction", 
		# we MUST reset re-upload flags so applicant sees "Returned for Correction" badge first, not "Draft".
		if self.overall_status == "Returned for Correction" and old_status != "Returned for Correction":
			self.has_reuploaded_items = 0
			for row in self.verification_items:
				row.is_reuploaded = 0

		# Also clear flags if finalized
		if self.overall_status in ["Verified", "Rejected"] and old_status != self.overall_status:
			self.has_reuploaded_items = 0
			for row in self.verification_items:
				row.is_reuploaded = 0

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
			# Move to background to avoid UI lag during synchronous email sending
			frappe.enqueue(
				method="slcm.pace.doctype.pace_document_verification.pace_document_verification.send_final_notification_bg",
				docname=self.name,
				now=frappe.flags.in_test
			)

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

			# Prepare headers to ensure CC recipients see the correct 'To' address
			email_headers = {
				"To": recipient,
				"Cc": ", ".join(cc_list) if cc_list else None
			}

			# 3. Send Email (now=True = sent immediately, avoids background worker delays)
			try:
				# We use now=True to bypass the Email Queue and send directly.
				# This fixes issues where background workers are stalled on the live server.
				frappe.sendmail(
					recipients=[recipient],
					cc=cc_list,
					subject=subject,
					message=message,
					reference_doctype=self.doctype,
					reference_name=self.name,
					now=True
				)
				# Log successful dispatch
				frappe.logger().info(f"PACE Verification Email sent successfully to {recipient} for {self.name}")
			except Exception:
				# If immediate sending fails (e.g. SMTP timeout), log it and fallback to Queueing
				frappe.log_error(traceback.format_exc(), f"PACE Verification Email Immediate Dispatch Failed (Fallback to Queue): {self.name}")
				try:
					frappe.sendmail(
						recipients=[recipient],
						cc=cc_list,
						subject=subject,
						message=message,
						reference_doctype=self.doctype,
						reference_name=self.name,
						now=False
					)
				except Exception:
					pass # Already logged the main failure

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

	def send_reupload_notification_to_verifier(self):
		"""
		Sends an email notification to the assigned verifier.
		"""
		try:
			if not self.assigned_verifier:
				# Log but don't fail, maybe notify an admin or common group
				frappe.log_error(f"No verifier assigned for {self.name}. Cannot send re-upload notification.", "PACE Verification Notification Error")
				return

			# Identify re-uploaded items
			reuploaded_items = [item for item in self.verification_items if item.is_reuploaded]
			if not reuploaded_items:
				return

			template_name = "PACE Document Re-uploaded for Verification"
			args = {
				"doc": self,
				"reuploaded_items": reuploaded_items,
				"assigned_verifier_name": frappe.db.get_value("User", self.assigned_verifier, "full_name"),
				"pace_verification_url": get_url(f"/app/pace-document-verification/{self.name}")
			}
			
			if not frappe.db.exists("Email Template", template_name):
				# Fallback if template doesn't exist yet
				subject = f"Action Required: Documents Re-uploaded for Application {self.application} - {self.applicant_name}"
				
				# Generate a simple table for fallback
				rows = ""
				for item in reuploaded_items:
					rows += f"<tr><td>{item.document_name}</td></tr>"
				
				message = f"""
				<p>Dear {args['assigned_verifier_name'] or 'Verifier'},</p>
				<p>The applicant <strong>{self.applicant_name}</strong> has re-uploaded documents for their application (<strong>{self.application}</strong>) and has submitted them for your verification.</p>
				<p><strong>Re-uploaded Documents:</strong></p>
				<table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
					<thead>
						<tr style="background-color: #f2f2f2;">
							<th align="left">Document Name</th>
						</tr>
					</thead>
					<tbody>
						{rows}
					</tbody>
				</table>
				<p>Please review the updated documents and proceed with the verification process.</p>
				<p><a href="{args['pace_verification_url']}">View Verification Record</a></p>
				"""
			else:
				email_template = frappe.get_doc("Email Template", template_name)
				subject = frappe.render_template(email_template.subject, args)
				if email_template.get("use_html"):
					message = frappe.render_template(email_template.response_html, args)
				else:
					message = frappe.render_template(email_template.response, args)
				
				if not message:
					message = frappe.render_template(email_template.get("message") or "", args)

			try:
				# Use now=True to bypass the Email Queue and send directly to verifier.
				frappe.sendmail(
					recipients=[self.assigned_verifier],
					subject=subject,
					message=message,
					reference_doctype=self.doctype,
					reference_name=self.name,
					now=True
				)
				# Log successful dispatch
				frappe.logger().info(f"PACE Verifier Re-upload Notification sent successfully to {self.assigned_verifier} for {self.name}")
			except Exception:
				# Fallback to Email Queue if immediate sending fails
				frappe.log_error(traceback.format_exc(), f"PACE Verifier Notification Immediate Dispatch Failed (Fallback to Queue): {self.name}")
				try:
					frappe.sendmail(
						recipients=[self.assigned_verifier],
						subject=subject,
						message=message,
						reference_doctype=self.doctype,
						reference_name=self.name,
						now=False
					)
				except Exception:
					pass
		except Exception:
			frappe.log_error(traceback.format_exc(), f"PACE Re-upload Notification Failed: {self.name}")

@frappe.whitelist()
def submit_for_verification(name):
	"""
	Whitelisted function for applicants to notify the verifier after re-uploading documents.
	"""
	if not name:
		frappe.throw(_("Missing verification name"))
		
	doc = frappe.get_doc("PACE Document Verification", name)
	
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to perform this action"), frappe.PermissionError)
	
	# Ensure the applicant is the owner or the application email matches
	applicant_email = frappe.db.get_value("PACE Application", doc.application, "email_address")
	if frappe.session.user != applicant_email and frappe.session.user != doc.owner and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Unauthorized access"), frappe.PermissionError)

	if doc.overall_status != "Returned for Correction":
		frappe.throw(_("This action is only available when the status is 'Returned for Correction'."))

	# Update verification status back to Pending as requested
	doc.db_set("overall_status", "Pending")
	doc.db_set("has_reuploaded_items", 1)
	
	# Update all re-uploaded items to Pending status and ensure is_reuploaded stays checked
	for item in doc.verification_items:
		if item.is_reuploaded:
			# Direct DB update on child row to change status and maintain re-upload flag
			frappe.db.set_value("PACE Verification Item", item.name, {
				"status": "Pending",
				"is_reuploaded": 1
			})

	# Send notification to verifier
	doc.send_reupload_notification_to_verifier()
	
	return {
		"status": "success",
		"message": _("Documents submitted for verification. The verifier has been notified.")
	}

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

def send_final_notification_bg(docname):
	"""
	Background job wrapper for sending the final verification notification.
	"""
	try:
		doc = frappe.get_doc("PACE Document Verification", docname)
		doc.send_final_verification_notification()
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Background Notification Failed for {docname}")

