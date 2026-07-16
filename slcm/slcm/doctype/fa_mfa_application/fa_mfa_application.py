
# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
import os
from frappe.model.document import Document
from frappe.utils import getdate, date_diff

class FAMFAApplication(Document):
	def before_save(self):
		self.rename_proof_document()

	def rename_proof_document(self):
		"""Prefix the document name to proof_document filename to avoid collisions across students."""
		if not self.proof_document or not self.name:
			return

		prefix = self.name + "_"

		# Look up the File doc to get the real file_url on disk
		file_doc = frappe.db.get_value("File", {
			"file_url": self.proof_document,
			"attached_to_doctype": self.doctype,
			"attached_to_name": self.name
		}, "name")
		if not file_doc:
			file_doc = frappe.db.get_value("File", {"file_url": self.proof_document}, "name")

		if not file_doc:
			return

		file_obj = frappe.get_doc("File", file_doc)
		actual_url = file_obj.file_url  # authoritative path on disk
		actual_basename = os.path.basename(actual_url)

		if actual_basename.startswith(prefix):
			return  # already renamed

		new_basename = prefix + actual_basename
		is_private = actual_url.startswith("/private/")
		new_url = ("/private/files/" if is_private else "/files/") + new_basename

		base_dir = "private" if is_private else "public"
		old_path = frappe.get_site_path(base_dir, actual_url.lstrip("/"))
		new_path = frappe.get_site_path(base_dir, new_url.lstrip("/"))

		if os.path.exists(old_path) and not os.path.exists(new_path):
			os.rename(old_path, new_path)

		file_obj.file_name = new_basename
		file_obj.file_url = new_url
		file_obj.db_update()

		self.proof_document = new_url

	def validate(self):
		self.validate_dates()
		self.validate_approval_status()

	def after_insert(self):
		try:
			self.notify_stakeholders()
		except Exception:
			# Notification failures (e.g. no outgoing Email Account configured) must
			# never block the student's application from being created.
			frappe.log_error(
				title="FA/MFA Application: notify_stakeholders failed",
				message=frappe.get_traceback(),
			)

	def notify_stakeholders(self):
		"""
		Email the Programme Chair(s) and AAD Team on record in Examination Settings
		whenever a student raises an FA/MFA application, using the configured Email
		Template. Each recipient gets their own individual email (not a shared
		To/Cc list). AAD Team is notified for visibility only — approval is still
		restricted to the Programme Chair role via the doctype's own permissions.
		"""
		settings = frappe.get_single("Examination Settings")

		programme_chairs = {row.user for row in settings.programme_chair_users if row.user}
		aad_team = {row.user for row in settings.aad_team_users if row.user} - programme_chairs

		if not programme_chairs and not aad_team:
			return

		template_name = settings.fa_mfa_email_template or "FA MFA Application Raised"
		try:
			template_doc = frappe.get_doc("Email Template", template_name)
		except frappe.DoesNotExistError:
			frappe.log_error(
				title="FA/MFA Application: notification template missing",
				message=f"Email Template '{template_name}' not found. Set it in Examination Settings → FA/MFA Notification Email Template.",
			)
			return

		application_url = frappe.utils.get_url_to_form(self.doctype, self.name)
		base_context = {
			"student_name": self.student_name,
			"course_name": self.course_name or self.course,
			"application_type": self.application_type,
			"reason": self.reason,
			"examination_date": self.examination_date,
			"application_name": self.name,
			"application_url": application_url,
		}

		def _send_to(user, role_note):
			recipient_name = frappe.db.get_value("User", user, "full_name") or user
			context = {**base_context, "recipient_name": recipient_name, "role_note": role_note}
			formatted = template_doc.get_formatted_email(context)
			try:
				frappe.sendmail(
					recipients=[user],
					subject=formatted["subject"],
					message=formatted["message"],
					reference_doctype=self.doctype,
					reference_name=self.name,
					now=True,
				)
			except Exception:
				frappe.log_error(
					title=f"FA/MFA Application: email failed ({user})",
					message=frappe.get_traceback(),
				)

		for user in programme_chairs:
			_send_to(user, "You can approve or reject this application.")

		for user in aad_team:
			_send_to(user, "This is for your information only — the Programme Chair holds approval rights.")

	def validate_approval_status(self):
		if self.status == "Approved":
			if not self.approver:
				self.approver = frappe.session.user
		
		if self.status == "Rejected":
			if not self.rejection_reason:
				frappe.throw("Rejection Reason is required when rejecting an application.")
			if not self.approver:
				self.approver = frappe.session.user

	def validate_dates(self):
		if not self.examination_date:
			return

		settings = frappe.get_single("Examination Settings")
		if not settings.allow_fa_mfa:
			frappe.throw("FA/MFA Applications are currently disabled in Examination Settings.")

		exam_date = getdate(self.examination_date)
		today = getdate()
		
		# If applying strictly for University Representation (Competitions), check dates
		if self.reason == "University Representation":
			if not self.event_from_date or not self.event_to_date:
				frappe.throw("Event dates are required for University Representation.")
			
			event_from = getdate(self.event_from_date)
			event_to = getdate(self.event_to_date)
			
			# Rule: participation dates fall within three days of the exam
			# Logic: Check if exam_date is within [event_from - 3 days, event_to + 3 days]
			# Or if the event overlaps with Exam Date +/- 3 days window.
			# Simplified Interpretation: The event happened within 3 days (before/after/during) of the exam.
			
			days_diff_from = date_diff(exam_date, event_from) # exam - event_start
			days_diff_to = date_diff(event_to, exam_date)     # event_end - exam
			
			# Check if event is too far in past or future relative to exam
			# Distance between interval [event_from, event_to] and point exam_date should be <= 3
			
			# If exam is BEFORE event:
			if exam_date < event_from:
				gap = date_diff(event_from, exam_date)
			# If exam is AFTER event:
			elif exam_date > event_to:
				gap = date_diff(exam_date, event_to)
			else:
				# During event
				gap = 0
				
			if gap > 3:
				frappe.throw("For University Representation, participation dates must be within 3 days of the examination date.")

			# Application Submit Window Rule
			days_before = settings.fa_application_days_before_exam or 10
			if date_diff(exam_date, today) < days_before:
				# Check if it is a "late" application which is allowed but requires justification
				pass 

		# General Check: Application shouldn't be too old if applying AFTER exam?
		if date_diff(today, exam_date) > (settings.fa_application_days_after_exam or 10):
			if self.reason != "University Representation": 
				frappe.msgprint("Warning: Application is submitted more than 10 days after the examination.")

	def on_submit(self):
		if self.status != "Approved":
			frappe.throw("Only Approved applications can be submitted.")
		self.trigger_attendance_recalculation()

	def on_cancel(self):
		self.trigger_attendance_recalculation()

	def on_trash(self):
		self.trigger_attendance_recalculation()

	def trigger_attendance_recalculation(self):
		"""
		Recalculate attendance for the Student and Course linked to this application.
		Since FA/MFA applies to a Course, we need to find relevant Course Offerings.
		"""
		try:
			# Find Course Offerings for this Course
			offerings = frappe.get_all("Course Offering", filters={"course_title": self.course}, pluck="name")
			
			if not offerings:
				return

			from slcm.slcm.utils.attendance_calculator import calculate_student_attendance
			
			for offering in offerings:
				# Synchronous call for immediate UI update
				# This handles getting or creating the summary proactively
				calculate_student_attendance(self.student, offering)
				
		except Exception as e:
			frappe.log_error(f"FA/MFA Recalc Error: {str(e)}")
