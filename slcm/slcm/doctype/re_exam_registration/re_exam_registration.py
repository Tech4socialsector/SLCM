# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ReExamRegistration(Document):
    def validate(self):
        if self.is_new():
            existing = frappe.db.get_value(
                "Re Exam Registration",
                {
                    "student": self.student,
                    "exam_plan": self.exam_plan,
                    "course": self.course,
                    "status": ["!=", "Cancelled"],
                },
                "name",
            )
            if existing:
                frappe.throw(
                    f"A re-exam registration already exists for this student and course: {existing}"
                )
