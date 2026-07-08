# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
import os
from frappe.model.document import Document
from frappe.utils import flt

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
		self.validate_shortage()
		
		# Auto-fill approver
		if self.final_status in ["Approved", "Rejected"] and not self.approver:
			self.approver = frappe.session.user
	
	def validate_shortage(self):
		"""Ensure student actually has a shortage before allowing application"""
		# Only validate on new application, not during approval process
		if self.is_new():
			# Fetch current summary
			summary = frappe.db.get_value("Attendance Summary", 
				{"student": self.student, "course_offering": self.course_offering}, 
				["attendance_percentage"], as_dict=True)
			
			if not summary:
				# Force calculation if summary doesn't exist
				from slcm.slcm.utils.attendance_calculator import calculate_student_attendance
				summary_data = calculate_student_attendance(self.student, self.course_offering)
				summary = frappe._dict(summary_data)
			
			settings = frappe.get_single("Attendance Settings")
			min_req = flt(settings.minimum_attendance_percentage)
			
			min_condonation_percentage = flt(settings.condonation_min_percentage) or 66.0
			
			if summary.attendance_percentage < min_condonation_percentage:
				frappe.throw(f"⚠️ Your attendance is less than the required {min_condonation_percentage}%, so you cannot apply for condonation.")

			if summary.attendance_percentage >= min_req:
				frappe.msgprint("Warning: Student already has sufficient attendance.", alert=True)

	def on_submit(self):
		if self.final_status != "Approved":
			frappe.throw("Only Approved applications can be submitted")
			
		self.trigger_recalculation()
	
	def on_cancel(self):
		self.trigger_recalculation()
		
	def trigger_recalculation(self):
		from slcm.slcm.utils.attendance_calculator import calculate_student_attendance
		calculate_student_attendance(self.student, self.course_offering)
		