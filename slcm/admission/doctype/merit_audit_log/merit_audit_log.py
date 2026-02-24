
import frappe
from frappe.model.document import Document

class MeritAuditLog(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw("Merit Audit Logs are immutable and cannot be modified.")

    def on_trash(self):
        frappe.throw("Merit Audit Logs cannot be deleted.")
