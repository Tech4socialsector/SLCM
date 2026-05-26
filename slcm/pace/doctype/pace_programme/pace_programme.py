# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document


class PACEProgramme(Document):
	def before_save(self):
		self.generate_program_slug()
		self.generate_application_form_link()

	def generate_application_form_link(self):
		if self.route:
			from frappe.utils import get_url
			web_form_route = frappe.db.get_value("Web Form", "PACE Application Form", "route") or "pace-application-form"
			self.application_form_link = f"{get_url()}/{web_form_route}/new?programme={self.route}"

	def generate_program_slug(self):
		if not self.programme_name:
			return

		base_slug = self._slugify(self.programme_name)

		# Check for clash with other PACE Programme records
		existing = frappe.db.get_value(
			"PACE Programme",
			{"route": base_slug, "name": ("!=", self.name)},
			"name"
		)

		if existing:
			# Append the system name (unique) to resolve clash
			self.route = base_slug + "-" + self._slugify(self.name)
		else:
			self.route = base_slug

	@staticmethod
	def _slugify(text):
		slug = text.lower()
		slug = slug.replace("&", "and")
		slug = re.sub(r"[()]", "", slug)
		slug = re.sub(r"[^a-z0-9\s-]", "", slug)
		slug = re.sub(r"[\s-]+", "-", slug)
		return slug.strip("-")
