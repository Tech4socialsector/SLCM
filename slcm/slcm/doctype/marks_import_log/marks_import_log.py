# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname


class MarksImportLog(Document):
	def autoname(self):
		self.name = make_autoname("IMP-LOG-.#####")
