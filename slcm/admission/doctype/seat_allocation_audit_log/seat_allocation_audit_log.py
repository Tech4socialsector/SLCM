import frappe
from frappe.model.document import Document

class SeatAllocationAuditLog(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw("Seat Allocation Audit Logs are immutable and cannot be modified.")

    def on_trash(self):
        frappe.throw("Seat Allocation Audit Logs cannot be deleted.")
