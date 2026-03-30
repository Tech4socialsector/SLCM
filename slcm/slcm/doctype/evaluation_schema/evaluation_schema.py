# Copyright (c) 2026, CU and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EvaluationSchema(Document):
	def validate(self):
		self.validate_component_marks()

	def validate_component_marks(self):
		if not self.schema_components:
			return
		custom_components = [c for c in self.schema_components if self._get_component_type(c.component) == "Custom"]
		total = sum(c.effective_max_marks or 0 for c in custom_components)
		if custom_components and total != self.total_marks:
			frappe.throw(
				f"Sum of effective maximum marks ({total}) must equal schema total marks = {self.total_marks}"
			)

	def _get_component_type(self, component_name):
		if component_name:
			return frappe.db.get_value("Exam Component", component_name, "component_type") or "Custom"
		return "Custom"
