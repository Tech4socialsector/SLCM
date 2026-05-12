# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ReExamCourseSetting(Document):
	def validate(self):
		existing = frappe.db.get_value(
			"Re Exam Course Setting",
			{"exam_plan": self.exam_plan, "course": self.course},
			"name",
		)
		if existing and existing != self.name:
			frappe.throw(
				f"A Re-Exam setting for Exam Plan <b>{self.exam_plan}</b> and "
				f"Course <b>{self.course}</b> already exists."
			)
