# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class UGDegreeDetail(Document):
	def validate(self):
		if self.ug_program:
			self.ug_program = self.ug_program.upper()
		if self.college:
			self.college = self.college.upper()
