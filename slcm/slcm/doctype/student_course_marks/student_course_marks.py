# Copyright (c) 2026, CU and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StudentCourseMarks(Document):
	def validate(self):
		self._calculate_total()

	def _calculate_total(self):
		total = 0.0
		for row in self.marks_entries:
			total += float(row.moderated_marks or row.marks or 0)
		self.total_marks = total
