import traceback

import frappe
from frappe.model.document import Document
from frappe.utils import get_url, getdate, now_datetime, today

class PACEApplicantFeeAssignment(Document):
	def validate(self):
		self.calculate_totals()

	def on_update(self):
		"""
		Triggered after status changes or manual updates.
		"""
		doc_before_save = self.get_doc_before_save()
		prev_status = doc_before_save.status if doc_before_save else None

		if self.status == "Paid" and prev_status != "Paid":
			self.on_payment_paid()
		
		if self.status == "Enrolled" and prev_status != "Enrolled":
			self.on_enrollment()

	def on_enrollment(self):
		"""
		Logic to handle enrollment: Notifications + Toast.
		"""
		# Avoid duplicate enrollment notifications for the same applicant in a single request/process
		notification_flag = f"enrollment_notification_sent_{self.applicant}"
		if not frappe.flags.get(notification_flag):
			self.send_enrollment_confirmation_email()
			self.send_enrollment_system_notification()
			frappe.flags[notification_flag] = True
			frappe.msgprint(frappe._("Enrollment confirmed! Confirmation email has been sent to {0}.").format(self.applicant_name), alert=True)

		self.update_user_roles()

	def update_user_roles(self):
		"""
		Updates user roles and profiles: Applicant -> Student
		"""
		try:
			applicant_email = frappe.db.get_value("PACE Application", self.applicant, "email_address")
			if applicant_email:
				user_name = frappe.db.get_value("User", {"email": applicant_email}, "name")
				if user_name:
					user = frappe.get_doc("User", user_name)
					roles_updated = False
					
					# Add Student role if not present
					if not user.has_role("Student"):
						user.add_roles("Student")
						roles_updated = True
					
					# Remove Applicant role if present
					if user.has_role("Applicant"):
						user.remove_roles("Applicant")
						roles_updated = True
					
					# Remove Applicant Role Profile if present
					if user.get("role_profiles"):
						initial_profiles = len(user.role_profiles)
						user.set("role_profiles", [p for p in user.role_profiles if p.role_profile != "Applicant"])
						if len(user.role_profiles) < initial_profiles:
							roles_updated = True
						
					if roles_updated:
						user.save(ignore_permissions=True)
						frappe.logger().info(f"[PACE Enrollment] User {user_name} updated: Added Student role, Removed Applicant role/profile")
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"PACE Enrollment User Role Update Failed: {self.name}")

	def send_enrollment_system_notification(self):
		"""
		Creates a Notification Log entry for the applicant upon enrollment.
		"""
		try:
			applicant_email = frappe.db.get_value("PACE Application", self.applicant, "email_address")
			if not applicant_email:
				return

			if frappe.db.exists("User", applicant_email):
				message_body = f"""
					<p>Congratulations! You have been successfully enrolled in <strong>{self.program}</strong>.</p>
					<p>Application Reference: <strong>{self.applicant}</strong></p>
					<p><a href="/pace_progress_tracker?app={self.applicant}" style="color: #920c24; font-weight: bold;">Click here to track your progress.</a></p>
				"""
				
				frappe.get_doc({
					"doctype": "Notification Log",
					"subject": "PACE Enrollment Confirmed",
					"for_user": applicant_email,
					"type": "Alert",
					"email_content": message_body,
					"document_type": self.doctype,
					"document_name": self.name,
					"from_user": frappe.session.user or "Administrator",
					"link": f"/pace_progress_tracker?app={self.applicant}"
				}).insert(ignore_permissions=True)
				
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"PACE Enrollment System Notification Failed: {self.name}")

	def send_enrollment_confirmation_email(self):
		"""
		Sends an enrollment confirmation email to the applicant using the 'PACE Student Enrollment Confirmation' 
		Email Template record from the database.
		"""
		try:
			# 1. Get Applicant Email from PACE Application
			applicant_email = frappe.db.get_value("PACE Application", self.applicant, "email_address")
			if not applicant_email:
				frappe.log_error(f"No email address found for applicant {self.applicant} (Fee Assignment: {self.name})", "PACE Enrollment Email Error")
				return

			# 2. Load Email Template from Database
			template_name = "PACE Student Enrollment Confirmation"
			if not frappe.db.exists("Email Template", template_name):
				frappe.log_error(
					f"Email Template '{template_name}' not found in database. Please ensure it is created.",
					"PACE Enrollment Email Template Missing"
				)
				return
			
			email_template = frappe.get_doc("Email Template", template_name)
			
			# 3. Prepare Jinja Arguments
			args = {
				"doc": self,
				"frappe": frappe
			}

			# 4. Render Subject and Message
			subject = frappe.render_template(email_template.subject or "Enrollment Confirmation", args)
			
			message = ""
			if email_template.get("use_html") and email_template.get("response_html"):
				message = frappe.render_template(email_template.response_html, args)
			elif email_template.get("response"):
				message = frappe.render_template(email_template.response, args)
			else:
				message = frappe.render_template(email_template.get("message") or "", args)

			cc_list = []
			cc_field_value = email_template.get("cc")
			if cc_field_value:
				cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]

			# 5. Prepare Attachments (Admission Letter)
			attachments = []
			admission_letter_url = frappe.db.get_value("PACE Application", self.applicant, "admission_letter")
			if admission_letter_url:
				file_names = frappe.get_all("File", filters={"file_url": admission_letter_url}, limit=1)
				if file_names:
					file_doc = frappe.get_doc("File", file_names[0].name)
					attachments.append({
						"fname": file_doc.file_name,
						"fcontent": file_doc.get_content()
					})
					frappe.logger().info(f"PACE Enrollment Email: Attached admission letter {file_doc.file_name} from URL {admission_letter_url}")
				else:
					frappe.log_error(f"Could not find File record for Admission Letter URL: {admission_letter_url}", "PACE Enrollment Email Attachment Error")

			# 6. Dispatch: prefer background send (now=False) for better performance during bulk operations.
			try:
				sender = None
				if email_template.get("email_account"):
					sender = frappe.db.get_value("Email Account", email_template.email_account, "email_id") or email_template.email_account

				frappe.sendmail(
					recipients=[applicant_email],
					sender=sender,
					cc=cc_list,
					subject=subject,
					message=message,
					attachments=attachments or None,
					reference_doctype=self.doctype,
					reference_name=self.name,
					now=False,
				)
				frappe.logger().info(
					f"PACE student enrollment confirmation email queued for {applicant_email} for {self.name}"
				)
			except Exception:
				frappe.log_error(
					traceback.format_exc(),
					f"PACE Enrollment Confirmation Email Failed: {self.name}",
				)
			
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"PACE Enrollment Confirmation Email Failed: {self.name}")

	def on_payment_paid(self):
		"""
		Central logic to handle payment success: Receipt + Notifications + Toast.
		"""
		# 1. Ensure Receipt exists
		receipt_name = frappe.db.get_value("PACE Receipt", {"fee_assignment": self.name}, "name")
		if receipt_name:
			receipt = frappe.get_doc("PACE Receipt", receipt_name)
		else:
			receipt = self.create_receipt()

		if receipt:
			# Sync receipt URL back to fee assignment for easier tracking/email access
			self.db_set("fee_receipt", receipt.receipt, update_modified=False)
			self.fee_receipt = receipt.receipt
			
			# 2. Send Notifications
			self.send_payment_confirmation_email(receipt)
			self.send_system_notification()
			
			# 3. Update PACE Application status if Admission Fee is paid
			if self.fee_type == "Admission Fee":
				frappe.db.set_value("PACE Application", self.applicant, "status", "Fee Paid")
			
			# 4. Success Toast
			frappe.msgprint(frappe._("Payment confirmed! Confirmation email and receipt have been sent to {0}.").format(self.applicant_name), alert=True)

	def create_receipt(self):
		from slcm.pace.api import _create_pace_receipt
		receipt = _create_pace_receipt(self, self.get("transaction_id") or "Manual")
		return receipt

	def send_system_notification(self):
		"""
		Creates a Notification Log entry for the applicant in the system portal.
		"""
		try:
			applicant_email = frappe.db.get_value("PACE Application", self.applicant, "email_address")
			if not applicant_email:
				return

			if frappe.db.exists("User", applicant_email):
				message_body = f"""
					<p>Your payment for <strong>{self.fee_type}</strong> has been successfully received.</p>
					<p>Transaction ID: <strong>{self.transaction_id or 'Manual'}</strong></p>
					<p><a href="/pace_progress_tracker?app={self.applicant}" style="color: #920c24; font-weight: bold;">Click here to track your application.</a></p>
				"""
				
				frappe.get_doc({
					"doctype": "Notification Log",
					"subject": f"PACE Payment Received: {self.fee_type}",
					"for_user": applicant_email,
					"type": "Alert",
					"email_content": message_body,
					"document_type": self.doctype,
					"document_name": self.applicant,
					"from_user": frappe.session.user or "Administrator",
					"link": f"/pace_progress_tracker?app={self.applicant}"
				}).insert(ignore_permissions=True)
				
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"PACE Payment System Notification Failed: {self.name}")

	def send_payment_confirmation_email(self, receipt):
		"""
		Sends a payment confirmation email to the applicant using the 'PACE Payment Confirmation' 
		Email Template record from the database.
		"""
		try:
			# 1. Get Applicant Email from PACE Application
			applicant_email = frappe.db.get_value("PACE Application", self.applicant, "email_address")
			if not applicant_email:
				frappe.log_error(f"No email address found for applicant {self.applicant} (Fee Assignment: {self.name})", "PACE Payment Email Error")
				return

			# 2. Load Email Template from Database
			template_name = "PACE Payment Confirmation"
			if not frappe.db.exists("Email Template", template_name):
				frappe.log_error(
					f"Email Template '{template_name}' not found in database. Please ensure it is created.",
					"PACE Payment Email Template Missing"
				)
				return
			
			email_template = frappe.get_doc("Email Template", template_name)
			
			# 3. Prepare Jinja Arguments
			args = {
				"doc": self,
				"receipt": receipt,
				"frappe": frappe
			}

			# 4. Render Subject and Message
			subject = frappe.render_template(email_template.subject or "Payment Confirmation", args)
			
			message = ""
			if email_template.get("use_html") and email_template.get("response_html"):
				message = frappe.render_template(email_template.response_html, args)
			elif email_template.get("response"):
				message = frappe.render_template(email_template.response, args)
			else:
				message = frappe.render_template(email_template.get("message") or "", args)

			# 5. Prepare Attachments (Receipt PDF)
			attachments = []
			file_url = receipt.receipt
			if not file_url:
				receipt.reload()
				file_url = receipt.receipt

			if file_url:
				# Use get_all with limit to handle potential duplicates or exact match issues
				file_names = frappe.get_all("File", filters={"file_url": file_url}, limit=1)
				if file_names:
					file_doc = frappe.get_doc("File", file_names[0].name)
					attachments.append({
						"fname": file_doc.file_name,
						"fcontent": file_doc.get_content()
					})
					frappe.logger().info(f"PACE Payment Email: Attached file {file_doc.file_name} from URL {file_url}")
				else:
					frappe.log_error(f"Could not find File record for URL: {file_url}", "PACE Payment Email Attachment Error")
			else:
				frappe.log_error(f"Receipt record {receipt.name} has no file URL in 'receipt' field.", "PACE Payment Email Attachment Error")

			cc_list = []
			cc_field_value = email_template.get("cc")
			if cc_field_value:
				cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]

			# 6. Dispatch: prefer background send (now=False) for better performance during bulk operations.
			try:
				sender = None
				if email_template.get("email_account"):
					sender = frappe.db.get_value("Email Account", email_template.email_account, "email_id") or email_template.email_account

				frappe.sendmail(
					recipients=[applicant_email],
					sender=sender,
					cc=cc_list,
					subject=subject,
					message=message,
					attachments=attachments or None,
					reference_doctype=self.doctype,
					reference_name=self.name,
					now=False,
				)
				frappe.logger().info(
					f"PACE payment confirmation email queued for {applicant_email} for {self.name}"
				)
			except Exception:
				frappe.log_error(
					traceback.format_exc(),
					f"PACE Payment Confirmation Email Failed: {self.name}",
				)
			
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"PACE Payment Confirmation Email Failed: {self.name}")

	def calculate_totals(self):
		total_amount = 0
		if self.fee_components:
			for row in self.fee_components:
				total_amount += row.total_amount
		else:
			# If no components, use the total_amount already set (useful for application fee)
			total_amount = self.total_amount
		
		self.total_amount = total_amount
		self.final_payable_amount = total_amount

def send_course_fee_reminders():
	"""
	Scheduled task (daily at 10:00 AM) to send reminders for unpaid course fees.
	Criteria:
	- Status is "Assigned"
	- Before admission closing date
	- Sent once per day
	"""
	# Find assignments that are "Assigned" (meaning fee is pending)
	assignments = frappe.get_all("PACE Applicant Fee Assignment", filters={
		"status": "Assigned",
		"fee_type": "Admission Fee"
	}, fields=["name", "applicant", "applicant_name", "program", "academic_year", "last_course_fee_reminder_sent"])

	for data in assignments:
		# Check if already sent today
		if data.last_course_fee_reminder_sent:
			last_sent = getdate(data.last_course_fee_reminder_sent)
			if last_sent == getdate(today()):
				continue

		# Get admission closing date
		admission_data = frappe.db.get_value("PACE Admission", 
			{"academic_year": data.academic_year, "status": "Active"}, 
			["admission_close_date", "status"], as_dict=True)
		
		if not admission_data or not admission_data.admission_close_date:
			# Fallback if no active admission found for that year
			admission_data = frappe.db.get_value("PACE Admission", 
				{"academic_year": data.academic_year}, 
				["admission_close_date", "status"], as_dict=True)

		if not admission_data or not admission_data.admission_close_date:
			continue

		# Only send if today is on or before closing date
		if getdate(today()) > getdate(admission_data.admission_close_date):
			continue

		assignment_doc = frappe.get_doc("PACE Applicant Fee Assignment", data.name)
		
		if send_course_fee_reminder_email(assignment_doc, admission_data.admission_close_date):
			send_course_fee_reminder_system_notification(assignment_doc, admission_data.admission_close_date)
			assignment_doc.db_set("last_course_fee_reminder_sent", now_datetime(), update_modified=False)
			frappe.db.commit()

def send_course_fee_reminder_email(doc, admission_close_date):
	"""
	Sends the course fee reminder email using 'PACE Course Fee Payment Reminder' template.
	"""
	template_name = "PACE Course Fee Payment Reminder"
	
	# Get Applicant Email
	applicant_email = frappe.db.get_value("PACE Application", doc.applicant, "email_address")
	if not applicant_email:
		return False

	if not frappe.db.exists("Email Template", template_name):
		frappe.log_error(f"Email Template '{template_name}' not found.", "PACE Fee Reminder Error")
		return False

	args = {
		"doc": doc,
		"admission_close_date": frappe.utils.formatdate(admission_close_date),
		"admission_portal_url": get_url("/admissions"),
	}

	email_template = frappe.get_doc("Email Template", template_name)
	
	try:
		subject = frappe.render_template(email_template.subject or "Course Fee Payment Reminder", args)
		
		message = ""
		if email_template.get("use_html") and email_template.get("response_html"):
			message = frappe.render_template(email_template.response_html, args)
		elif email_template.get("response"):
			message = frappe.render_template(email_template.response, args)
		else:
			message = frappe.render_template(email_template.get("message") or "", args)

		if message:
			sender = None
			if email_template.get("email_account"):
				sender = frappe.db.get_value("Email Account", email_template.email_account, "email_id") or email_template.email_account

			frappe.sendmail(
				recipients=[applicant_email],
				sender=sender,
				subject=subject,
				message=message,
				reference_doctype=doc.doctype,
				reference_name=doc.name,
				now=False
			)
			return True
	except Exception:
		frappe.log_error(traceback.format_exc(), f"PACE Course Fee Reminder Email Failed: {doc.name}")
	
	return False

def send_course_fee_reminder_system_notification(doc, admission_close_date):
	"""
	Creates a Notification Log entry for course fee reminder.
	"""
	try:
		# Get Applicant Email
		applicant_email = frappe.db.get_value("PACE Application", doc.applicant, "email_address")
		if not applicant_email:
			return

		if frappe.db.exists("User", applicant_email):
			formatted_date = frappe.utils.formatdate(admission_close_date)
			message_body = f"""
				<p>Dear {doc.applicant_name},</p>
				<p>Your payment for the <strong>{doc.fee_type}</strong> for <strong>{doc.program}</strong> is pending.</p>
				<p>Please complete the payment before the deadline: <strong>{formatted_date}</strong>.</p>
				<p><a href="/pace_progress_tracker?app={doc.applicant}" style="color: #920c24; font-weight: bold;">Click here to PAY NOW.</a></p>
			"""
			
			frappe.get_doc({
				"doctype": "Notification Log",
				"subject": "Course Fee Payment Reminder",
				"for_user": applicant_email,
				"type": "Alert",
				"email_content": message_body,
				"document_type": doc.doctype,
				"document_name": doc.name,
				"from_user": frappe.session.user or "Administrator",
				"link": f"/pace_progress_tracker?app={doc.applicant}"
			}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(traceback.format_exc(), f"PACE Course Fee Reminder Notification Failed: {doc.name}")
