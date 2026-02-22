
import frappe
from frappe.model.document import Document

class AdmissionAuditLog(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw("Admission Audit Logs are immutable and cannot be modified.")

    def on_trash(self):
        frappe.throw("Admission Audit Logs cannot be deleted.")
