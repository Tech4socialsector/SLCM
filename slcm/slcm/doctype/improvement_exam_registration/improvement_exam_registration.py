import frappe
from frappe.model.document import Document


class ImprovementExamRegistration(Document):
    def validate(self):
        if self.is_new():
            existing = frappe.db.get_value(
                "Improvement Exam Registration",
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
                    f"An improvement exam registration already exists for this student and course: {existing}"
                )
