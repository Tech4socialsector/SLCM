# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class GradingSchema(Document):
	def validate(self):
		self._validate_grade_ranges()

	def _validate_grade_ranges(self):
		for table_field in ("grades", "reexam_grades"):
			rows = self.get(table_field) or []
			for row in rows:
				if row.marks_from is None or row.marks_to is None:
					frappe.throw(f"Grade '{row.grade}': marks_from and marks_to are required.")
				if float(row.marks_from) > float(row.marks_to):
					frappe.throw(
						f"Grade '{row.grade}': marks_from ({row.marks_from}) cannot exceed marks_to ({row.marks_to})."
					)
				if float(row.marks_to) > float(self.maximum_marks or 100):
					frappe.throw(
						f"Grade '{row.grade}': marks_to ({row.marks_to}) exceeds maximum_marks ({self.maximum_marks})."
					)

	def get_grade(self, marks, use_reexam=False):
		"""Return grade symbol for given marks. Returns '' if no matching range."""
		rows = self.reexam_grades if (use_reexam and self.use_reexam_composition) else self.grades
		return self._match_grade_row(float(marks), rows or [])

	def get_grade_point(self, marks, use_reexam=False):
		"""Return grade point (float) for given marks."""
		rows = self.reexam_grades if (use_reexam and self.use_reexam_composition) else self.grades
		for row in (rows or []):
			if self._in_range(float(marks), row):
				return float(row.grade_point or 0)
		return 0.0

	def is_failed(self, marks, use_reexam=False):
		"""Return True if marks fall into a grade row with failed=1."""
		rows = self.reexam_grades if (use_reexam and self.use_reexam_composition) else self.grades
		for row in (rows or []):
			if self._in_range(float(marks), row):
				return bool(row.failed)
		return False

	# ── helpers ──────────────────────────────────────────────────────────────

	def _match_grade_row(self, marks, rows):
		for row in rows:
			if self._in_range(marks, row):
				return row.grade or ""
		return ""

	def _in_range(self, marks, row):
		low_ok = (marks >= float(row.marks_from)) if (row.from_operator or ">=") == ">=" else (marks > float(row.marks_from))
		high_ok = (marks <= float(row.marks_to)) if (row.to_operator or "<=") == "<=" else (marks < float(row.marks_to))
		return low_ok and high_ok


@frappe.whitelist()
def get_grade_for_marks(grading_schema, marks, use_reexam=0):
	"""API: return grade, grade_point, is_failed for given schema + marks."""
	doc = frappe.get_doc("Grading Schema", grading_schema)
	m = float(marks)
	re = bool(int(use_reexam))
	return {
		"grade": doc.get_grade(m, re),
		"grade_point": doc.get_grade_point(m, re),
		"is_failed": doc.is_failed(m, re),
	}
