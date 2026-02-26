import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import now_datetime

class ScholarshipUtilization(Document):
	def autoname(self):
		if not self.admission_cycle:
			frappe.throw(frappe._("Admission Cycle is mandatory for naming"))
		
		cycle_code = frappe.db.get_value("Admission Cycle", self.admission_cycle, "cycle_code")
		if not cycle_code:
			frappe.throw(frappe._("Cycle Code not found in Admission Cycle {0}").format(self.admission_cycle))
		
		# Naming Series: SU-{CYCLE}-.#####
		self.name = make_autoname(f"SU-{cycle_code}-.#####")

	def validate(self):
		self.calculate_remaining_budget()
		self.set_audit_fields()

	def calculate_remaining_budget(self):
		self.remaining_budget = (self.total_budget or 0) - (self.allocated_amount or 0)

	def set_audit_fields(self):
		self.last_updated_on = now_datetime()
		self.last_updated_by = frappe.session.user
