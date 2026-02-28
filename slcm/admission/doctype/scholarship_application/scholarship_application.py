# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import now_datetime


class ScholarshipApplication(Document):
	def autoname(self):
		if not self.admission_cycle:
			frappe.throw(frappe._("Admission Cycle is mandatory for naming"))
		
		cycle_code = frappe.db.get_value("Admission Cycle", self.admission_cycle, "cycle_code")
		if not cycle_code:
			frappe.throw(frappe._("Cycle Code not found in Admission Cycle {0}").format(self.admission_cycle))
		
		# Naming Series: SA-{CYCLE}-.#####
		self.name = make_autoname(f"SA-{cycle_code}-.#####")

	def validate(self):
		self.validate_rejection()
		self.handle_approval_locking()

	def validate_rejection(self):
		if self.status == "Rejected" and not self.rejection_reason:
			frappe.throw(frappe._("Rejection Reason is mandatory if status is Rejected"))

	def handle_approval_locking(self):
		if self.status == "Approved":
			if not self.approved_by:
				self.approved_by = frappe.session.user
			if not self.approval_date:
				self.approval_date = now_datetime()
			
			# Logic for locking can be handled by Frappe permissions or by checking status in hooks/methods
			# Here we just ensure approval details are set.
