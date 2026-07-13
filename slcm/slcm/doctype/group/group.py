# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Group(Document):
	def validate(self):
		self.validate_capacity()

	def validate_capacity(self):
		if self.capacity is not None and self.capacity <= 0:
			frappe.throw(_("Capacity must be greater than zero"))
