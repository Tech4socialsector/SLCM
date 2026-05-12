# Copyright (c) 2025, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CourseOffering(Document):
	def validate(self):
		self._validate_capacity()

	def _validate_capacity(self):
		if not self.maximum_students:
			return
		enrolled = frappe.db.count(
			"Course Enrollment",
			{"course_offering": self.name, "enrollment_status": "Enrolled"},
		)
		if enrolled >= self.maximum_students:
			frappe.throw(
				_("Course Offering {0} has reached its maximum capacity of {1} students").format(
					self.name, self.maximum_students
				)
			)
