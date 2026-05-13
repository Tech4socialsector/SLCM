# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PromotionPolicy(Document):
	def validate(self):
		if self.from_year >= self.to_year:
			frappe.throw("'To Year' must be greater than 'From Year'.")
		if self.enable_cgpa_check and not self.min_cgpa:
			frappe.throw("Please set a Minimum CGPA value when CGPA Check is enabled.")
		if self.enable_attendance_check and not self.min_attendance_percent:
			frappe.throw("Please set a Minimum Attendance % when Attendance Check is enabled.")
		if self.enable_course_shortage_check and (self.max_shortage_courses is None or self.max_shortage_courses < 0):
			frappe.throw("Please set Max Courses with Attendance Shortage (0 or more) when Course Shortage Check is enabled.")
		if self.enable_cf_check and (self.max_cf_fa_shortage is None or self.max_cf_fa_shortage < 0):
			frappe.throw("Please set Max CF Courses with FA + Shortage (0 or more) when Carry-Forward Check is enabled.")
