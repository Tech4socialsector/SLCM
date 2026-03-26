# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ExamSchema(Document):
	def validate(self):
		self.validate_duplicate_components()
		self.validate_total_effective_marks()
		self.validate_assessments()

	def validate_duplicate_components(self):
		"""Prevent duplicate components in the table."""
		seen = set()
		for row in self.components or []:
			if row.exam_component in seen:
				frappe.throw(
					_("Duplicate component '{0}' found in row {1}. Each component can only be added once.").format(
						row.exam_component, row.idx
					)
				)
			seen.add(row.exam_component)

	def validate_total_effective_marks(self):
		"""Validate that sum of effective max marks equals total marks."""
		if not self.components:
			return

		total_effective = sum(flt(row.effective_max_marks) for row in self.components)
		self.total_effective_marks = total_effective

		if flt(self.total_marks) and total_effective != flt(self.total_marks):
			frappe.msgprint(
				_("Sum of effective maximum marks ({0}) does not equal schema total marks ({1}).").format(
					total_effective, self.total_marks
				),
				indicator="orange",
				alert=True,
			)

	def validate_assessments(self):
		"""Validate nested assessments for Custom components."""
		if not self.components:
			return

		# Get custom components
		custom_components = []
		for row in self.components:
			ctype = frappe.db.get_value("Exam Component", row.exam_component, "component_type")
			if ctype == "Custom":
				custom_components.append(row)

		if not custom_components:
			return

		for comp_row in custom_components:
			assn_total = 0
			for assn in self.assessments or []:
				if assn.exam_component == comp_row.exam_component:
					assn_total += flt(assn.maximum_marks)
			
			if flt(comp_row.effective_max_marks) > 0 and assn_total != flt(comp_row.effective_max_marks):
				frappe.msgprint(
					_("For Component '{0}', sum of assessment maximum marks ({1}) must be equal to component effective total marks ({2}).").format(
						comp_row.label or comp_row.exam_component, assn_total, comp_row.effective_max_marks
					),
					indicator="orange",
					alert=True
				)
