import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import now_datetime

class ScholarshipAuditLog(Document):
	def autoname(self):
		if not self.admission_cycle:
			frappe.throw(frappe._("Admission Cycle is mandatory for naming"))
		
		cycle_code = frappe.db.get_value("Admission Cycle", self.admission_cycle, "cycle_code")
		if not cycle_code:
			frappe.throw(frappe._("Cycle Code not found in Admission Cycle {0}").format(self.admission_cycle))
		
		# Naming Series: SAL-{CYCLE}-.#####
		self.name = make_autoname(f"SAL-{cycle_code}-.#####")

def log_scholarship_action(scholarship_application, scholarship_scheme, admission_cycle, campus, program, action_type, new_state, previous_state=None, reason=None, triggered_by="Admin"):
	"""
	Helper function to log scholarship actions.
	"""
	doc = frappe.get_doc({
		"doctype": "Scholarship Audit Log",
		"scholarship_application": scholarship_application,
		"scholarship_scheme": scholarship_scheme,
		"admission_cycle": admission_cycle,
		"campus": campus,
		"program": program,
		"action_type": action_type,
		"previous_state": frappe.as_json(previous_state) if previous_state else None,
		"new_state": frappe.as_json(new_state),
		"performed_by": frappe.session.user,
		"triggered_by": triggered_by,
		"action_timestamp": now_datetime(),
		"reason": reason or f"{action_type} performed by {frappe.session.user}",
		"ip_address": frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None
	})
	doc.insert(ignore_permissions=True)
	return doc.name
