# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now


class StudentGrievance(Document):
	def before_insert(self):
		if not self.submitted_on:
			from frappe.utils import today
			self.submitted_on = today()

	def on_update(self):
		if self.status in ("Resolved", "Closed") and not self.resolved_on:
			self.resolved_by = frappe.session.user
			self.resolved_on = now()
			self.db_set("resolved_by", self.resolved_by, update_modified=False)
			self.db_set("resolved_on", self.resolved_on, update_modified=False)
