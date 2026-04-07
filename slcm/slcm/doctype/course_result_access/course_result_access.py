# Copyright (c) 2026, CU and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CourseResultAccess(Document):

	def validate(self):
		# Auto-lock when edit access is revoked — but never auto-unlock
		# (manual LOCKED status is preserved even when edit_access is ON)
		if not self.edit_access:
			self.status = "LOCKED"

	def before_save(self):
		# Revoking rules per the UI notes:
		# 1. Auto-generate grade and grade report are revoked when mask_student_info is ON
		if self.mask_student_info:
			self.auto_generate_grade_access = 0
			self.generate_grade_report = 0
		# 2. Grade access fields are revoked when the record is LOCKED or edit_access is OFF
		if self.status == "LOCKED" or not self.edit_access:
			self.auto_generate_grade_access = 0
			self.edit_grade_access = 0
