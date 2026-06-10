import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import get_url
import traceback
from slcm.pace.assignment_logic import is_user_on_leave, assign_verifier_round_robin

class PACEDocumentVerification(Document):
	def onload(self):
		from frappe.utils import getdate, nowdate
		if self.status == "Pending" and self.due_date and getdate(self.due_date) < getdate(nowdate()) and not self.is_overdue:
			self.is_overdue = 1
			self.db_set("is_overdue", 1)

	def validate(self):
		self.validate_remarks()
		self.ensure_programme_column()
		self.prevent_child_deletion_or_modification()

		# Automatically compute is_overdue based on due date
		from frappe.utils import getdate, nowdate
		if self.status == "Pending" and self.due_date and getdate(self.due_date) < getdate(nowdate()):
			self.is_overdue = 1
		else:
			self.is_overdue = 0

		# Prevent non-managers from editing due_date
		if not self.is_new() and not self.flags.ignore_permissions:
			old_doc = self.get_doc_before_save()
			if old_doc and str(old_doc.due_date or "") != str(self.due_date or ""):
				user_roles = frappe.get_roles()
				manager_roles = {"System Manager", "Academic Manager", "PACE Admission Manager", "Admission Admin", "PACE Verification Admin", "Document Verification Admin"}
				is_manager = any(role in user_roles for role in manager_roles)
				if not is_manager:
					frappe.throw(_("You are not authorized to modify the Due Date."))


	def prevent_child_deletion_or_modification(self):
		if self.is_new():
			return

		user_roles = frappe.get_roles()
		manager_roles = {"System Manager", "Academic Manager", "PACE Admission Manager", "Admission Admin"}
		is_manager = any(role in user_roles for role in manager_roles)
		is_verifier = "Document Verifier" in user_roles

		if is_verifier and not is_manager:
			old_doc = self.get_doc_before_save()
			if old_doc:
				# Map of old item name -> file URL
				old_items = {item.name: item.file for item in old_doc.verification_items}
				
				# Current items in the doc
				current_items = {item.name: item.file for item in self.verification_items if item.name}
				
				# 1. Check for deleted or modified items
				for old_name, old_file in old_items.items():
					if old_name not in current_items:
						frappe.throw(_("You are not allowed to delete verification items/files."))
					elif current_items[old_name] != old_file:
						frappe.throw(_("You are not allowed to modify or delete the files stored in the child table."))
				
				# 2. Check for added items
				for item in self.verification_items:
					if not item.name:
						frappe.throw(_("You are not allowed to add new verification items."))

	def ensure_programme_column(self):
		"""
		Temporary fix for Permission Error: Ensure 'programme' column exists in DB.
		"""
		try:
			columns = frappe.db.get_table_columns(self.doctype)
			if "programme" not in columns:
				frappe.db.sql(f"ALTER TABLE `tab{self.doctype}` ADD COLUMN `programme` varchar(255)")
				frappe.clear_cache(doctype=self.doctype)
				frappe.msgprint(_("Database updated: 'programme' column added."), indicator='green', alert=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "PACE DB Fix Error")

	def validate_remarks(self):
		for row in self.verification_items:
			if row.status == "Returned for Correction" and not row.remarks:
				frappe.throw(frappe._("Remarks are required for returned document: {0}").format(row.document_name))

	def before_save(self):
		"""
		Clean up flags when status is changed by verifier.
		"""
		doc_before_save = self.get_doc_before_save()
		if not doc_before_save:
			return

		old_status = doc_before_save.status
		
		# If verifier changes status to "Returned for Correction", 
		# we MUST reset re-upload flags so applicant sees "Returned for Correction" badge first, not "Draft".
		if self.status == "Returned for Correction" and old_status != "Returned for Correction":
			self.has_reuploaded_items = 0
			for row in self.verification_items:
				row.is_reuploaded = 0

		# Also clear flags if finalized or returned
		if self.status in ["Verified", "Rejected", "Returned for Correction"] and old_status != self.status:
			self.has_reuploaded_items = 0
			self.is_overdue = 0
			for row in self.verification_items:
				row.is_reuploaded = 0

	def on_update(self):
		"""
		Trigger summary notification when status changes or when forced (Finalize button).
		"""
		doc_before_save = self.get_doc_before_save()
		old_status = doc_before_save.status if doc_before_save else "Pending"
		
		# Trigger conditions:
		# 1. Status changed to a final state (Verified/Returned/Rejected)
		# 2. Or the 'force_notification' flag is set (from the Finalize button)
		is_final_status = self.status in ["Verified", "Returned for Correction", "Rejected"]
		status_changed = self.status != old_status
		
		if is_final_status and (status_changed or self.flags.force_notification):
			self.send_final_verification_notification()
			if self.status in ["Verified", "Rejected"]:
				self.send_verifier_confirmation_email()
		
		# Manual Reassignment Sync Logic
		# Triggered when assigned_verifier changes
		old_verifier = doc_before_save.assigned_verifier if doc_before_save else None
		if self.assigned_verifier and self.assigned_verifier != old_verifier:
			from slcm.pace.assignment_logic import update_verifier_permissions
			from slcm.pace.doctype.pace_assignment_log.pace_assignment_log import create_assignment_log
			
			# 1. Sync permissions and ToDo (Always required for UI/Access)
			update_verifier_permissions(self.name, old_verifier, self.assigned_verifier)
			
			# 2. Create Audit Log
			create_assignment_log(self, old_verifier, self.assigned_verifier)
			
			# 3. Add Timeline Comment
			self.add_comment("Info", _("Verifier changed from {0} to {1}").format(old_verifier or "None", self.assigned_verifier))

			# 4. Send the email only if not explicitly ignored (e.g. bulk re-assignment)
			if not self.flags.ignore_assignment_email:
				from slcm.pace.assignment_logic import send_verifier_assignment_email
				send_verifier_assignment_email(self.assigned_verifier, [self])

	def send_final_verification_notification(self):
		"""
		Sends a comprehensive summary email and system notification.
		"""
		try:
			if self.status == "Rejected":
				template_name = "PACE Document Verification Rejected"
			else:
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
			
			from slcm.pace.api import _get_active_pace_admission_name
			pace_adm_name = _get_active_pace_admission_name()
			admission_close_date = None
			if pace_adm_name:
				admission_close_date = frappe.db.get_value("PACE Admission", pace_adm_name, "admission_close_date")

			args = {
				"doc": self,
				"admission_portal_url": get_url("/admissions"),
				"institution_name": inst_settings.institution_name,
				"admission_close_date": frappe.utils.formatdate(admission_close_date) if admission_close_date else ""
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

			# 3. Send Email (now=False = queued for background sending)
			try:
				# We use now=False to queue the email.
				# This ensures the process is fast and background workers handle the SMTP.
				sender = None
				if email_template.get("email_account"):
					sender = frappe.db.get_value("Email Account", email_template.get("email_account"), "email_id") or email_template.get("email_account")

				frappe.sendmail(
					recipients=[recipient],
					sender=sender,
					cc=cc_list,
					subject=subject,
					message=message,
					reference_doctype=self.doctype,
					reference_name=self.name,
					now=False
				)
				# Log successful queueing
				frappe.logger().info(f"PACE Verification Email queued successfully to {recipient} for {self.name}")
			except Exception:
				frappe.log_error(traceback.format_exc(), f"PACE Verification Email Queueing Failed: {self.name}")

			# 4. Create System Notification
			if frappe.db.exists("User", recipient):
				# Use a cleaner version for system notification if available
				notification_message = message
				if email_template.get("response"):
					try:
						notification_message = frappe.render_template(email_template.response, args)
					except Exception:
						notification_message = message
				
				# Strip Gmail mobile auto-shrink fix if it's still there
				if "Gmail mobile auto-shrink fix" in notification_message:
					import re
					notification_message = re.sub(r'<!-- Gmail mobile auto-shrink fix -->.*?</div>', '', notification_message, flags=re.DOTALL)

				frappe.get_doc({
					"doctype": "Notification Log",
					"subject": f"Document Verification Update: {self.status}",
					"for_user": recipient,
					"type": "Alert",
					"email_content": notification_message,
					"document_type": self.doctype,
					"document_name": self.name,
					"from_user": frappe.session.user or "Administrator",
					"link": f"/pace_progress_tracker?app={self.application}"
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
			
			from slcm.pace.api import _get_active_pace_admission_name
			pace_adm_name = _get_active_pace_admission_name()
			admission_close_date = None
			if pace_adm_name:
				admission_close_date = frappe.db.get_value("PACE Admission", pace_adm_name, "admission_close_date")

			args = {
				"doc": self,
				"reuploaded_items": reuploaded_items,
				"assigned_verifier_name": frappe.db.get_value("User", self.assigned_verifier, "full_name"),
				"pace_verification_url": get_url(f"/app/pace-document-verification/{self.name}"),
				"admission_close_date": frappe.utils.formatdate(admission_close_date) if admission_close_date else ""
			}
			
			cc_list = []
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

				cc_field_value = email_template.get("cc")
				if cc_field_value:
					cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]

			try:
				# Use now=False to queue the email.
				sender = None
				if 'email_template' in locals() and email_template and email_template.get("email_account"):
					sender = frappe.db.get_value("Email Account", email_template.get("email_account"), "email_id") or email_template.get("email_account")

				frappe.sendmail(
					recipients=[self.assigned_verifier],
					sender=sender,
					cc=cc_list,
					subject=subject,
					message=message,
					reference_doctype=self.doctype,
					reference_name=self.name,
					now=False,
				)
				frappe.logger().info(
					f"PACE Verifier Re-upload Notification queued successfully for {self.assigned_verifier} for {self.name}"
				)
			except Exception:
				frappe.log_error(
					traceback.format_exc(),
					f"PACE Verifier Notification Queueing Failed: {self.name}",
				)

			# Send System Notification to verifier
			if frappe.db.exists("User", self.assigned_verifier):
				# Use a cleaner version for system notification if available
				notification_message = message
				if 'email_template' in locals() and email_template.get("response"):
					try:
						notification_message = frappe.render_template(email_template.response, args)
					except Exception:
						notification_message = message
				
				# Strip Gmail mobile auto-shrink fix if it's still there
				if "Gmail mobile auto-shrink fix" in notification_message:
					import re
					notification_message = re.sub(r'<!-- Gmail mobile auto-shrink fix -->.*?</div>', '', notification_message, flags=re.DOTALL)

				frappe.get_doc({
					"doctype": "Notification Log",
					"subject": f"Action Required: Documents Re-uploaded - {self.applicant_name}",
					"for_user": self.assigned_verifier,
					"type": "Alert",
					"email_content": notification_message,
					"document_type": self.doctype,
					"document_name": self.name,
					"from_user": frappe.session.user or "Administrator",
					"link": f"/app/pace-document-verification/{self.name}"
				}).insert(ignore_permissions=True)

		except Exception:
			frappe.log_error(traceback.format_exc(), f"PACE Re-upload Notification Failed: {self.name}")

	def send_verifier_confirmation_email(self):
		"""
		Sends a confirmation email to the verifier after they finalize a verification.
		"""
		try:
			if not self.assigned_verifier:
				return

			template_name = "PACE Verifier Action Confirmation"
			
			if not frappe.db.exists("Email Template", template_name):
				return

			email_template = frappe.get_doc("Email Template", template_name)
			
			args = {
				"doc": self,
				"verifier_name": frappe.db.get_value("User", self.assigned_verifier, "full_name") or "Verifier"
			}

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

			sender = None
			if email_template.get("email_account"):
			    sender = frappe.db.get_value("Email Account", email_template.get("email_account"), "email_id") or email_template.get("email_account")

			frappe.sendmail(
			    recipients=[self.assigned_verifier],
			    sender=sender,
			    cc=cc_list,
			    subject=subject,
			    message=message,
			    reference_doctype=self.doctype,
			    reference_name=self.name,
			    now=False
			)
			
			# Create System Notification for Verifier
			if frappe.db.exists("User", self.assigned_verifier):
				# Use a cleaner version for system notification if available
				notification_message = message
				if 'email_template' in locals() and email_template.get("response"):
					try:
						notification_message = frappe.render_template(email_template.response, args)
					except Exception:
						notification_message = message
				
				# Strip Gmail mobile auto-shrink fix if it's still there
				if "Gmail mobile auto-shrink fix" in notification_message:
					import re
					notification_message = re.sub(r'<!-- Gmail mobile auto-shrink fix -->.*?</div>', '', notification_message, flags=re.DOTALL)

				frappe.get_doc({
					"doctype": "Notification Log",
					"subject": f"Verification Finalized - {self.applicant_name}",
					"for_user": self.assigned_verifier,
					"type": "Alert",
					"email_content": notification_message,
					"document_type": self.doctype,
					"document_name": self.name,
					"from_user": frappe.session.user or "Administrator",
					"link": f"/app/pace-document-verification/{self.name}"
				}).insert(ignore_permissions=True)

			frappe.logger().info(f"PACE Verifier Confirmation Email queued for {self.assigned_verifier} for {self.name}")

		except Exception:
			frappe.log_error(traceback.format_exc(), f"PACE Verifier Confirmation Email Failed: {self.name}")

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

	if doc.status != "Returned for Correction":
		frappe.throw(_("This action is only available when the status is 'Returned for Correction'."))

	# Update verification status back to Pending as requested
	doc.db_set("status", "Pending")
	doc.db_set("has_reuploaded_items", 1)
	
	# Extend due date on re-upload based on configuration
	from slcm.pace.assignment_logic import get_sla_days
	from frappe.utils import add_days, nowdate
	days = get_sla_days(doc.application)
	doc.db_set("due_date", add_days(nowdate(), days))
	doc.db_set("is_overdue", 0)
	
	# Update all re-uploaded items to Pending status and ensure is_reuploaded stays checked
	for item in doc.verification_items:
		if item.is_reuploaded:
			# Direct DB update on child row to change status and maintain re-upload flag
			frappe.db.set_value("PACE Verification Item", item.name, {
				"status": "Pending",
				"is_reuploaded": 1
			})

	# --- New Re-assignment Logic on Re-upload ---
	# If the currently assigned verifier is on leave, find someone else
	if doc.assigned_verifier and is_user_on_leave(doc.assigned_verifier):
		frappe.logger().info(f"PACE: Re-assigning {doc.name} because {doc.assigned_verifier} is on leave.")
		assign_verifier_round_robin(doc, force_reassign=True)
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
	
	# Send notification to verifier
	doc.send_reupload_notification_to_verifier()
	
	return {
		"status": "success",
		"message": _("Documents submitted for verification. The verifier has been notified.")
	}

def get_permission_query_conditions(user=None):
	# Dynamically mark overdue records in DB on list/query request
	from frappe.utils import nowdate
	try:
		frappe.db.sql("""
			UPDATE `tabPACE Document Verification`
			SET is_overdue = 1
			WHERE status = 'Pending'
			  AND due_date IS NOT NULL
			  AND due_date < %s
			  AND is_overdue = 0
		""", (nowdate(),))
		frappe.db.commit()
	except Exception:
		pass

	if not user:
		user = frappe.session.user

	# Absolute bypass for the master Administrator user
	if user == "Administrator":
		return ""

	roles = frappe.get_roles(user)
	
	# Manager Bypass: If they have any of these roles, they see everything (even if they are also a verifier)
	manager_roles = {"System Manager", "Academic Manager", "PACE Admission Manager", "Admission Admin"}
	if any(role in roles for role in manager_roles):
		return ""

	# Verifier Restriction: Only see assigned records
	verifier_roles = {"Document Verifier", "Faculty", "Guest Faculty"}
	if any(role in roles for role in verifier_roles):
		return f"assigned_verifier = {frappe.db.escape(user)}"

	# Applicant Restriction: Only see own records
	if "Applicant" in roles:
		return f"owner = {frappe.db.escape(user)}"

	# Default: Allow all if they have the role but aren't restricted
	return ""

def has_permission(doc, ptype, user):
	roles = frappe.get_roles(user)
	
	manager_roles = {"System Manager", "Academic Manager", "PACE Admission Manager", "Admission Admin"}
	if any(role in roles for role in manager_roles):
		return True
	
	verifier_roles = {"Document Verifier", "Faculty", "Guest Faculty"}
	if any(role in roles for role in verifier_roles) and doc.assigned_verifier == user:
		return True
		
	if "Applicant" in roles and doc.owner == user:
		return True
	
	return False
