# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ClassConfiguration(Document):
    def validate(self):
        self.validate_seat_limit()
        self.auto_generate_class_name()
    
    def validate_seat_limit(self):
        """Validate that number of students doesn't exceed seat limit"""
        if self.seat_limit and self.students:
            student_count = len(self.students)
            if student_count > self.seat_limit:
                frappe.throw(f"Number of students ({student_count}) exceeds seat limit ({self.seat_limit})")
    
    def auto_generate_class_name(self):
        """Auto-generate class name if not provided"""
        if not self.class_name:
            parts = []
            if self.course:
                parts.append(self.course)
            if self.type:
                parts.append(self.type)
            if self.batch:
                parts.append(self.batch)
            if self.section:
                parts.append(self.section)
            
            if parts:
                self.class_name = " - ".join(parts)


def _enrolled_student_ids(programme, batch, section):
    """Students enrolled (via Student Enrollment) in this programme/batch,
    and in this section if given - but an enrollment with NO section set yet
    still counts as a match. Student Enrollment.section was only added
    recently, so most existing enrollments predate it and are blank; treating
    "not yet assigned" as excluded would make every section-scoped class
    invisible to students who simply haven't been assigned a section yet."""
    if not batch:
        return []

    base_filters = {"batch": batch, "status": "Enrolled"}
    if programme:
        base_filters["program"] = programme

    if not section:
        return frappe.get_all("Student Enrollment", filters=base_filters, pluck="student")

    exact = frappe.get_all(
        "Student Enrollment", filters={**base_filters, "section": section}, pluck="student"
    )
    unassigned = frappe.get_all(
        "Student Enrollment", filters={**base_filters, "section": ["is", "not set"]}, pluck="student"
    )
    return list(dict.fromkeys(exact + unassigned))


@frappe.whitelist()
def get_students_by_filter(programme=None, batch=None, section=None):
    """Get students enrolled in this programme/batch/section, via Student Enrollment
    (the actual source of truth for who is enrolled - Student Master has no batch/
    section field of its own to filter by)."""
    student_ids = _enrolled_student_ids(programme, batch, section)
    if not student_ids:
        return []

    return frappe.get_all(
        "Student Master",
        filters={"name": ["in", student_ids]},
        fields=["name", "first_name", "middle_name", "last_name", "registration_id", "email"],
    )


@frappe.whitelist()
def student_query(doctype, txt, searchfield, start, page_len, filters):
    """Link-field query for the Students grid: only show students actually
    enrolled (via Student Enrollment) in this class's programme/batch/section.
    Student Master has no batch/section field of its own to filter by."""
    filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})

    student_ids = _enrolled_student_ids(filters.get("programme"), filters.get("batch"), filters.get("section"))
    if not student_ids:
        return []

    or_filters = {}
    if txt:
        or_filters = {"name": ["like", f"%{txt}%"], "first_name": ["like", f"%{txt}%"]}

    return frappe.get_all(
        "Student Master",
        filters={"name": ["in", student_ids]},
        or_filters=or_filters,
        fields=["name", "first_name"],
        as_list=True,
        limit_start=start,
        limit_page_length=page_len,
    )
