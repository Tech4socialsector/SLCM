# Copyright (c) 2025, Nishanth and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class AttendanceSummary(Document):
	def autoname(self):
		from frappe.model.naming import make_autoname
		# Deterministic name based on Student and Course Offering
		if self.student and self.course_offering:
			# Create a hash or structured ID to ensure uniqueness.
			# Using a hash is safer for length limits (140 chars max for name).
			# Format: ASU-{Student}-{Hash(CourseOffering)}
			import hashlib
			offering_hash = hashlib.md5(self.course_offering.encode("utf-8")).hexdigest()[:10]
			self.name = f"ASU-{self.student}-{offering_hash}"
		else:
			self.name = make_autoname("ASU-.YYYY.-.#####")
