# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class EmailTemplates(Document):
	def autoname(self):
		self.name = f"{self.title} - {self.version}"
