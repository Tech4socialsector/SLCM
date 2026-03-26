# Copyright (c) 2025, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class StudentEnrollment(Document):
    def validate(self):
        self.validate_duplicate_enrollment()

    def before_save(self):
        self.fetch_program_and_courses()

    def on_update(self):
        """Sync Student Master when enrollment status changes."""
        self._sync_student_master_status()

    def fetch_program_and_courses(self):
        if not self.program and self.cohort:
            self.program = frappe.db.get_value("Cohort", self.cohort, "program")

        if self.program and not self.enrolled_courses:
            program_doc = frappe.get_doc("Program", self.program)
            if program_doc.table_fela:
                for pc in program_doc.table_fela:
                    self.append("enrolled_courses", {
                        "course":       pc.course,
                        "course_name":  pc.course_name,
                        "course_type":  pc.course_type,
                        "course_status": pc.course_status,
                        "credit_value": pc.credit_value,
                    })

    def validate_duplicate_enrollment(self):
        """Prevent duplicate enrollment for same student + cohort + academic_year."""
        filters = {
            "student":       self.student,
            "cohort":        self.cohort,
            "academic_year": self.academic_year,
            "docstatus":     ["<", 2],
        }
        existing = frappe.db.exists("Student Enrollment", filters)
        if existing and existing != self.name:
            frappe.throw(_("Enrollment already exists for this student in the selected cohort"))

    def _sync_student_master_status(self):
        """When enrollment is dropped/completed, reflect on Student Master."""
        if not self.student:
            return
        if self.status == "Dropped":
            frappe.db.set_value("Student Master", self.student, {
                "student_status": "Dropped",
                "academic_status": "Inactive",
            })
        elif self.status == "Completed":
            frappe.db.set_value("Student Master", self.student, {
                "student_status": "Graduated",
            })
