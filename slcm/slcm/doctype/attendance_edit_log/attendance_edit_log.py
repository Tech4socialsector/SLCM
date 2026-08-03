# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AttendanceEditLog(Document):
	"""Track all changes to attendance records for audit purposes"""


@frappe.whitelist()
def log_attendance_edit(attendance_record, field_changed, old_value, new_value, edit_reason):
	"""Append an audit log entry for an attendance edit.

	One Attendance Edit Log exists per Student Attendance record; each edit
	is appended as a row to its edit_entries child table instead of creating
	a new parent document.
	"""
	existing_name = frappe.db.exists("Attendance Edit Log", {"attendance_record": attendance_record})
	if existing_name:
		log = frappe.get_doc("Attendance Edit Log", existing_name)
	else:
		log = frappe.get_doc({
			"doctype": "Attendance Edit Log",
			"attendance_record": attendance_record,
		})

	log.append("edit_entries", {
		"field_changed": field_changed,
		"old_value": str(old_value) if old_value else "",
		"new_value": str(new_value) if new_value else "",
		"edit_reason": edit_reason,
		"edited_by": frappe.session.user,
		"edit_timestamp": frappe.utils.now(),
	})

	if existing_name:
		log.save(ignore_permissions=True)
	else:
		log.insert(ignore_permissions=True)

	return log.name


@frappe.whitelist()
def get_attendance_edit_history(attendance_record):
	"""Get all edit entries for an attendance record"""
	log_name = frappe.db.exists("Attendance Edit Log", {"attendance_record": attendance_record})
	if not log_name:
		return []

	entries = frappe.get_all(
		"Attendance Edit Entry",
		filters={"parent": log_name, "parenttype": "Attendance Edit Log"},
		fields=[
			"field_changed", "old_value", "new_value",
			"edit_reason", "edited_by", "edit_timestamp",
		],
		order_by="edit_timestamp desc"
	)
	return entries
