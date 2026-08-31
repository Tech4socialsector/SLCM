# Copyright (c) 2026, Administrator and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class StipendPayment(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero."))

	def on_submit(self):
		self.db_set("status", "Submitted", update_modified=False)
		self._log_to_student("Submitted")

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
		self._log_to_student("Cancelled")

	def _log_to_student(self, status):
		from slcm.slcm.doctype.student_master.student_master import _append_stipend_log

		_append_stipend_log(self.student, self, status)
