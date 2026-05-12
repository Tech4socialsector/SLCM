# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StudentPromotion(Document):
	def before_save(self):
		if not self.processed_by:
			self.processed_by = frappe.session.user
		if not self.processed_on:
			from frappe.utils import now_datetime
			self.processed_on = now_datetime()
