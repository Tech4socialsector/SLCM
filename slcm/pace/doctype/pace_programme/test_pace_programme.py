# Copyright (c) 2026, TFSS and Contributors
# See license.txt

import re
import frappe
from frappe.tests import IntegrationTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestPACEProgramme(IntegrationTestCase):
	"""
	Integration tests for PACEProgramme.
	Use this class for testing interactions between multiple components.
	"""

	def test_generate_program_slug(self):
		# Clean up existing test records
		frappe.db.delete("PACE Programme", {"programme_name": ["in", ["Test Programme", "Test Programme!"]]})

		programme = frappe.get_doc({
			"doctype": "PACE Programme",
			"programme_name": "Test Programme",
			"programme_prefix": "Postgraduate in",
			"programme_code": "TP"
		})
		programme.insert()
		self.assertEqual(programme.route, "test-programme")

		# Test collision with a name that produces the same base slug
		programme2 = frappe.get_doc({
			"doctype": "PACE Programme",
			"programme_name": "Test Programme!",
			"programme_prefix": "Postgraduate in",
			"programme_code": "TP2"
		})
		programme2.insert()
		# The slug should be base_slug + "-" + slugified(name)
		# base_slug is "test-programme"
		# slugified(name) for "Postgraduate in Test Programme!" is "postgraduate-in-test-programme"
		# So it should be "test-programme-postgraduate-in-test-programme"
		self.assertEqual(programme2.route, "test-programme-postgraduate-in-test-programme")

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
