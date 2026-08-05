# Copyright (c) 2025, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CourseOffering(Document):
	def validate(self):
		self.validate_faculty_table_sections()
		self.sync_primary_faculty()

	def validate_faculty_table_sections(self):
		"""Each section can have only one Primary faculty; a section with no
		explicit faculty row (section left blank) is treated as "applies to
		the whole offering" and is checked separately."""
		if not self.faculty_table:
			return

		primary_sections = {}
		for row in self.faculty_table:
			if not row.is_primary:
				continue
			key = row.section or None
			if key in primary_sections:
				section_label = row.section or "the whole Course Offering"
				frappe.throw(
					f"Row {row.idx} and Row {primary_sections[key]}: only one faculty can be "
					f"marked Primary for {section_label}."
				)
			primary_sections[key] = row.idx

	def sync_primary_faculty(self):
		"""Keep the legacy `faculty` Link field in sync with the Faculty table.

		`faculty` is read directly (not via the child table) across student
		portal, parent portal, ID cards, timetable, office hours and the
		analytics dashboard, so it must always reflect a sensible value
		instead of being replaced outright by the child table. When faculty
		are split by section, the row with no section (or the first row) is
		used as the offering-level default.
		"""
		if not self.faculty_table:
			return

		unsectioned = [row for row in self.faculty_table if not row.section]
		candidates = unsectioned or self.faculty_table

		primary_rows = [row for row in candidates if row.is_primary]
		primary_row = primary_rows[0] if primary_rows else candidates[0]
		self.faculty = primary_row.faculty
