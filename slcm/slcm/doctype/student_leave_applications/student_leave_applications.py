# Copyright (c) 2025, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now, today, nowdate


class StudentLeaveApplications(Document):
	def before_insert(self):
		if not self.submitted_on:
			self.submitted_on = today()
		if not self.status:
			self.status = "Pending"

	def on_update(self):
		if self.status in ("Approved", "Rejected") and not self.reviewed_on:
			self.db_set("reviewed_by", frappe.session.user, update_modified=False)
			self.db_set("reviewed_on", now(), update_modified=False)
			self._send_leave_notification()

	def _send_leave_notification(self):
		try:
			from frappe.utils import formatdate, getdate

			status_label = self.status
			icon = "✅" if self.status == "Approved" else "❌"
			from_str = formatdate(self.from_date, "dd MMM yyyy") if self.from_date else "—"
			to_str   = formatdate(self.to_date,   "dd MMM yyyy") if self.to_date   else "—"
			days     = int(self.total_leave_days or 0)

			title = f"{icon} Leave Request {status_label} — {self.name}"

			content_lines = [
				f"<p>Your leave request <strong>{self.name}</strong> has been <strong>{status_label}</strong>.</p>",
				f"<p><strong>Period:</strong> {from_str} → {to_str} ({days} day(s))</p>",
			]
			if self.admin_remarks:
				content_lines.append(
					f"<p><strong>Remarks:</strong> {self.admin_remarks}</p>"
				)
			content = "".join(content_lines)

			ann = frappe.get_doc({
				"doctype": "Student Announcement",
				"title": title,
				"announcement_type": "Administrative",
				"priority": "Important",
				"publish_date": nowdate(),
				"is_active": 1,
				"target_audience": "Specific Student(s)",
				"target_students": [{"student": self.student}],
				"content": content,
			})
			ann.insert(ignore_permissions=True)
			frappe.db.commit()
		except Exception as e:
			frappe.log_error(f"Leave notification error for {self.name}: {e}", "Student Leave Applications")
