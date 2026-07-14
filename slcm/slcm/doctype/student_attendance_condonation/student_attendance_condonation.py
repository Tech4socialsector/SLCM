# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
import os
from frappe.model.document import Document
from frappe.utils import flt, add_days, getdate, now_datetime

def assign_round_robin_authority(config_doc, authority_table_fieldname, last_index_fieldname, programme):
	"""
	Mirrors slcm.pace.assignment_logic.assign_verifier_round_robin.
	"""
	authorities = config_doc.get(authority_table_fieldname)
	if not authorities:
		frappe.throw(f"No authorities configured in Attendance Condonation Configuration for {authority_table_fieldname}.")

	# Filter by programme
	valid_authorities = [a for a in authorities if a.programme == programme]
	if not valid_authorities:
		frappe.throw(f"No eligible authority found for programme '{programme}' in {authority_table_fieldname}.")

	last_index = config_doc.get(last_index_fieldname) or 0
	num_valid = len(valid_authorities)

	# Start searching from the next index
	start_idx = last_index % num_valid
	selected_row = valid_authorities[start_idx]

	# Increment the assigned counter
	frappe.db.set_value("Attendance Condonation Table", selected_row.name, "assigned", (selected_row.assigned or 0) + 1, update_modified=False)

	# Update the config doc's last assigned index
	new_index = (start_idx + 1) % num_valid
	frappe.db.set_value("Attendance Condonation Configuration", config_doc.name, last_index_fieldname, new_index, update_modified=False)

	return selected_row.authority


def send_condonation_email(template_fieldname, doc, recipients):
	config = frappe.get_single("Attendance Condonation Configuration")
	template_name = config.get(template_fieldname)
	if not template_name:
		return
	
	email_template = frappe.get_doc("Email Template", template_name)
	
	args = {
		"doc": doc,
		"student_name": doc.student_name,
		"course": frappe.db.get_value("Course Offering", doc.course_offering, "course_name") if doc.course_offering else "",
		"programme": doc.programme,
		"due_date": doc.aad_due_date if doc.final_status == "Pending" else doc.programme_chair_due_date,
		"remarks": doc.aad_remarks if doc.final_status == "Rejected" and doc.aad_rejected_reason else doc.programme_chair_remarks,
		"rejected_reason": doc.aad_rejected_reason if doc.final_status == "Rejected" and doc.aad_rejected_reason else doc.programme_chair_rejected_reason
	}
	
	subject = frappe.render_template(email_template.subject, args)
	if email_template.use_html:
		message = frappe.render_template(email_template.response_html, args)
	else:
		message = frappe.render_template(email_template.response, args)
		
	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=message,
		reference_doctype=doc.doctype,
		reference_name=doc.name
	)


class StudentAttendanceCondonation(Document):
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
		if not self.programme:
			frappe.throw("Programme is required. Please ensure the student is mapped to a Programme.")
	
	def before_submit(self):
		config = frappe.get_single("Attendance Condonation Configuration")
		self.aad_approver = assign_round_robin_authority(config, "level_one_authority", "l1_last_assigned_index", self.programme)
		self.submitted_date = now_datetime()
		if config.l1_due_days:
			self.aad_due_date = add_days(getdate(self.submitted_date), config.l1_due_days)
		self.final_status = "Pending"
		
		# Send assignment email
		if self.aad_approver:
			send_condonation_email("l1_assignment_email_template", self, [self.aad_approver])



	def on_submit(self):
		pass
	
	def on_cancel(self):
		self.trigger_recalculation()
		
	def trigger_recalculation(self):
		from slcm.slcm.utils.attendance_calculator import calculate_student_attendance
		calculate_student_attendance(self.student, self.course_offering)

	@frappe.whitelist()
	def aad_decision(self, action, remarks=None, rejected_reason=None):
		if frappe.session.user != self.aad_approver:
			frappe.throw("You are not authorized to make a decision on this document.")
		if self.final_status != "Pending":
			frappe.throw("Decision can only be made when status is Pending.")
			
		self.aad_approve_or_rejected_timestamp = now_datetime()
		config = frappe.get_single("Attendance Condonation Configuration")
		
		# Find child row to increment
		authorities = config.get("level_one_authority")
		matched_row = next((a for a in authorities if a.authority == self.aad_approver and a.programme == self.programme), None)
		
		if action == "approve":
			self.final_status = "May Be Approved"
			self.aad_remarks = remarks
			if matched_row:
				frappe.db.set_value("Attendance Condonation Table", matched_row.name, "approved", (matched_row.approved or 0) + 1, update_modified=False)
			
			# Assign PC
			self.programme_chair_approver = assign_round_robin_authority(config, "level_two_authority", "l2_last_assigned_index", self.programme)
			if config.l2_due_days:
				self.programme_chair_due_date = add_days(getdate(self.aad_approve_or_rejected_timestamp), config.l2_due_days)
				
			# Send emails
			student_email = frappe.db.get_value("Student Master", self.student, "official_email_id") or frappe.db.get_value("Student Master", self.student, "email")
			if student_email:
				send_condonation_email("l1_approval_email_template", self, [student_email])
			if self.programme_chair_approver:
				send_condonation_email("l2_assignment_email_template", self, [self.programme_chair_approver])
				
		elif action == "reject":
			if not rejected_reason:
				frappe.throw("Rejected Reason is mandatory.")
			self.final_status = "Rejected"
			self.aad_rejected_reason = rejected_reason
			if matched_row:
				frappe.db.set_value("Attendance Condonation Table", matched_row.name, "rejected", (matched_row.rejected or 0) + 1, update_modified=False)
				
			student_email = frappe.db.get_value("Student Master", self.student, "official_email_id") or frappe.db.get_value("Student Master", self.student, "email")
			if student_email:
				send_condonation_email("l1_rejected_email_template", self, [student_email])
				
		self.save(ignore_permissions=True)

	@frappe.whitelist()
	def programme_chair_decision(self, action, remarks=None, rejected_reason=None):
		if frappe.session.user != self.programme_chair_approver:
			frappe.throw("You are not authorized to make a decision on this document.")
		if self.final_status != "May Be Approved":
			frappe.throw("Decision can only be made when status is May Be Approved.")
			
		self.programme_chair_approve_or_rejected_timestamp = now_datetime()
		config = frappe.get_single("Attendance Condonation Configuration")
		
		# Find child row to increment
		authorities = config.get("level_two_authority")
		matched_row = next((a for a in authorities if a.authority == self.programme_chair_approver and a.programme == self.programme), None)
		
		if action == "approve":
			self.final_status = "Approved"
			self.programme_chair_remarks = remarks
			if matched_row:
				frappe.db.set_value("Attendance Condonation Table", matched_row.name, "approved", (matched_row.approved or 0) + 1, update_modified=False)
				
			student_email = frappe.db.get_value("Student Master", self.student, "official_email_id") or frappe.db.get_value("Student Master", self.student, "email")
			if student_email:
				send_condonation_email("l2_approval_email_template", self, [student_email])
				
			self.trigger_recalculation()
				
		elif action == "reject":
			if not rejected_reason:
				frappe.throw("Rejected Reason is mandatory.")
			self.final_status = "Rejected"
			# The fieldname has a typo: proramme_chair_rejected_reason
			self.proramme_chair_rejected_reason = rejected_reason
			if matched_row:
				frappe.db.set_value("Attendance Condonation Table", matched_row.name, "rejected", (matched_row.rejected or 0) + 1, update_modified=False)
				
			student_email = frappe.db.get_value("Student Master", self.student, "official_email_id") or frappe.db.get_value("Student Master", self.student, "email")
			if student_email:
				send_condonation_email("l2_rejected_email_template", self, [student_email])
				
		self.save(ignore_permissions=True)
		