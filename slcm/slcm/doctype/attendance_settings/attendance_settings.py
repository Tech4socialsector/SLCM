# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AttendanceSettings(Document):
	def validate(self):
		self._validate_percentage()
		self._validate_hours()
		self._validate_parent_alert()

	def _validate_percentage(self):
		if not (0 <= self.minimum_attendance_percentage <= 100):
			frappe.throw("Minimum attendance percentage must be between 0 and 100")

	def _validate_hours(self):
		if self.core_course_hours <= 0:
			frappe.throw("Core course hours must be greater than 0")
		if self.elective_course_hours <= 0:
			frappe.throw("Elective course hours must be greater than 0")
		if self.core_office_hours < 0:
			frappe.throw("Core office hours cannot be negative")
		if self.elective_office_hours < 0:
			frappe.throw("Elective office hours cannot be negative")

	def _validate_parent_alert(self):
		if not self.enable_parent_rfid_alert:
			return
		threshold = self.rfid_absence_threshold_hours or 0
		if not (1 <= threshold <= 72):
			frappe.throw("Absence Threshold must be between 1 and 72 hours")
		if (
			self.parent_alert_email_template
			and not frappe.flags.in_import
			and not frappe.db.exists("Email Template", self.parent_alert_email_template)
		):
			frappe.throw(f"Email Template '{self.parent_alert_email_template}' does not exist")


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_users_by_role(doctype, txt, searchfield, start, page_len, filters):
	role = filters.get("role")
	return frappe.db.sql("""
		select u.name, u.full_name
		from `tabUser` u
		inner join `tabHas Role` hr on hr.parent = u.name
		where hr.role = %(role)s
		  and u.enabled = 1
		  and u.name like %(txt)s
		order by u.name
		limit %(start)s, %(page_len)s
	""", {
		"role": role,
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	})
