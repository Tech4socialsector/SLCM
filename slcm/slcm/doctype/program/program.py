# Copyright (c) 2025, Nishanth and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document


class Program(Document):

	def before_save(self):
		self.generate_program_slug()

	def generate_program_slug(self):
		if not self.program_name:
			return

		base_slug = self._slugify(self.program_name)

		# Check for clash with other Program records
		existing = frappe.db.get_value(
			"Program",
			{"program_slug": base_slug, "name": ("!=", self.name)},
			"name"
		)

		if existing:
			# Append the system name (unique) to resolve clash
			self.program_slug = base_slug + "-" + self._slugify(self.name)
		else:
			self.program_slug = base_slug

	@staticmethod
	def _slugify(text):
		slug = text.lower()
		slug = slug.replace("&", "and")
		slug = re.sub(r"[()]", "", slug)
		slug = re.sub(r"[^a-z0-9\s-]", "", slug)
		slug = re.sub(r"[\s-]+", "-", slug)
		return slug.strip("-")