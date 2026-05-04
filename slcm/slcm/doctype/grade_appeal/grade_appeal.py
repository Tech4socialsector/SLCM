# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, now


class GradeAppeal(Document):
	def validate(self):
		if not self.submitted_on:
			self.submitted_on = today()
		self._check_duplicate()

	def _check_duplicate(self):
		existing = frappe.db.exists(
			"Grade Appeal",
			{
				"student": self.student,
				"exam_plan": self.exam_plan,
				"course": self.course,
				"appeal_type": self.appeal_type,
				"status": ["in", ["Submitted", "Under Review"]],
				"name": ["!=", self.name or ""],
			},
		)
		if existing:
			frappe.throw(
				f"An active appeal for this course and appeal type already exists ({existing})."
			)

	def on_update(self):
		if self.status in ("Resolved", "Rejected") and not self.resolved_on:
			self.db_set("resolved_on", now(), update_modified=False)
			self.db_set("resolved_by", frappe.session.user, update_modified=False)
