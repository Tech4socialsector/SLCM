# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TranscriptTemplate(Document):
	def before_save(self):
		# Only one template can be the default
		if self.is_default:
			frappe.db.set_value(
				"Transcript Template",
				{"name": ("!=", self.name), "is_default": 1},
				"is_default",
				0,
			)

	def validate(self):
		if not self.template_name:
			frappe.throw(frappe._("Template Name is required."))
