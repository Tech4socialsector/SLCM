# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class PGDegreeDetails(Document):
	def validate(self):
		if self.pg_program:
			self.pg_program = self.pg_program.upper()
		if self.collegeuniversity:
			self.collegeuniversity = self.collegeuniversity.upper()
