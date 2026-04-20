import traceback

import frappe
from frappe.model.document import Document

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
		self.send_enrollment_confirmation_email()
		frappe.msgprint(frappe._("Enrollment confirmed! Confirmation email has been sent to {0}.").format(self.applicant_name), alert=True)

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

			# 5. Dispatch: prefer background send (now=False) for better performance during bulk operations.
			try:
				frappe.sendmail(
					recipients=[applicant_email],
					cc=cc_list,
					subject=subject,
					message=message,
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
			# 2. Send Notifications
			self.send_payment_confirmation_email(receipt)
			self.send_system_notification()
			
			# 3. Success Toast
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
					<p><a href="/admissions" style="color: #920c24; font-weight: bold;">Click here to track your application.</a></p>
				"""
				
				frappe.get_doc({
					"doctype": "Notification Log",
					"subject": f"PACE Payment Received: {self.fee_type}",
					"for_user": applicant_email,
					"type": "Alert",
					"email_content": message_body,
					"document_type": self.doctype,
					"document_name": self.name,
					"from_user": frappe.session.user or "Administrator",
					"link": "/admissions"
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
			file_url = receipt.get("receipt")
			if not file_url:
				receipt.reload()
				file_url = receipt.get("receipt")

			if file_url:
				file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
				if file_name:
					file_doc = frappe.get_doc("File", file_name)
					attachments.append({
						"fname": file_doc.file_name,
						"fcontent": file_doc.get_content()
					})

			cc_list = []
			cc_field_value = email_template.get("cc")
			if cc_field_value:
				cc_list = [c.strip() for c in cc_field_value.replace(";", ",").split(",") if c.strip()]

			# 6. Dispatch: prefer background send (now=False) for better performance during bulk operations.
			try:
				frappe.sendmail(
					recipients=[applicant_email],
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
