# Copyright (c) 2025, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class StudentEnrollment(Document):
    def validate(self):
        self.validate_duplicate_enrollment()
        self._validate_cohort_seat_limit()
        self._validate_status_transition()

    def before_save(self):
        self.fetch_program_and_courses()

    def on_update(self):
        """Sync Student Master when enrollment status changes."""
        self._sync_student_master_status()
        self._refresh_batch_enrolled_count(self.cohort)
        if self.has_value_changed("cohort"):
            previous = self.get_doc_before_save()
            if previous and previous.cohort and previous.cohort != self.cohort:
                self._refresh_batch_enrolled_count(previous.cohort)

    def after_delete(self):
        self._refresh_batch_enrolled_count(self.cohort)

    def fetch_program_and_courses(self):
        if not self.program and self.cohort:
            self.program = frappe.db.get_value("Batch", self.cohort, "program")

        if self.program and self.cohort and not self.enrolled_courses:
            offerings = frappe.get_all(
                "Course Offering",
                filters={"cohort": self.cohort, "status": "Open"},
                fields=["name", "course_title"],
            )
            for offering in offerings:
                course_type = frappe.db.get_value("Course", offering.course_title, "course_type")
                self.append("enrolled_courses", {
                    "course_offering": offering.name,
                    "course":          offering.course_title,
                    "course_type":     course_type or "",
                    "status":          "Enrolled",
                })

    def _validate_cohort_seat_limit(self):
        """Block enrollment if cohort has reached its seat limit."""
        if not self.cohort:
            return
        seat_limit = frappe.db.get_value("Batch", self.cohort, "seat_limit")
        if not seat_limit:
            return
        existing_count = frappe.db.count(
            "Student Enrollment",
            {
                "cohort": self.cohort,
                "status": ["not in", ["Dropped"]],
                "name": ["!=", self.name or "__new__"],
                "docstatus": ["<", 2],
            },
        )
        if existing_count >= seat_limit:
            frappe.throw(
                _("Cohort {0} has reached its seat limit of {1}").format(self.cohort, seat_limit)
            )

    def _validate_status_transition(self):
        """Guard against status changes that don't make sense.

        Full lifecycle rules (e.g. Pending -> Enrolled -> Dropped/Completed
        ordering) are not enforced yet - only the one transition that is
        wrong under any policy: un-completing a Completed enrollment.
        Extend here once the intended lifecycle is finalized.
        """
        if not self.is_new() and self.has_value_changed("status"):
            previous = self.get_doc_before_save()
            if previous and previous.status == "Completed" and self.status != "Completed":
                frappe.throw(
                    _("Cannot change status from Completed to {0}").format(self.status)
                )

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

    def _refresh_batch_enrolled_count(self, cohort):
        """Recompute the Batch's total_enrolled_count from actual enrollments."""
        if not cohort or not frappe.db.exists("Batch", cohort):
            return
        count = frappe.db.count(
            "Student Enrollment",
            {
                "cohort": cohort,
                "status": ["not in", ["Dropped"]],
                "docstatus": ["<", 2],
            },
        )
        frappe.db.set_value("Batch", cohort, "total_enrolled_count", count, update_modified=False)

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


@frappe.whitelist()
def get_other_terms(student, exclude=None):
    """List a student's other Student Enrollment records (other terms),
    most recent academic year first, for the 'Other Terms' selector on
    the Student Enrollment form."""
    if not student:
        return []

    enrollments = frappe.get_all(
        "Student Enrollment",
        filters={"student": student, "docstatus": ["<", 2]},
        fields=["name", "academic_year", "term_name", "status"],
    )

    ay_names = {e.academic_year for e in enrollments if e.academic_year}
    ay_start = {}
    if ay_names:
        for ay in frappe.get_all(
            "Academic Year",
            filters={"name": ["in", list(ay_names)]},
            fields=["name", "year_start_date"],
        ):
            ay_start[ay.name] = ay.year_start_date

    enrollments.sort(key=lambda e: ay_start.get(e.academic_year) or "", reverse=True)

    return [e for e in enrollments if e.name != exclude]


@frappe.whitelist()
def bulk_update_enrollment_status(names, status):
    """Update status on multiple Student Enrollment records via save(),
    so validate() (duplicate/seat-limit/transition checks) still applies.
    """
    if isinstance(names, str):
        names = frappe.parse_json(names)

    updated, failed = [], []
    for name in names:
        try:
            doc = frappe.get_doc("Student Enrollment", name)
            doc.status = status
            doc.save()
            updated.append(name)
        except Exception as e:
            failed.append({"name": name, "error": str(e)})

    return {"updated": updated, "failed": failed}
