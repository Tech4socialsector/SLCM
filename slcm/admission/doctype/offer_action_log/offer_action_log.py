import frappe
from frappe import _
from frappe.model.document import Document
class OfferActionLog(Document):
    """
    Audit log for Offer Letter actions.
    This DocType is append-only for regulatory compliance.
    """
    def validate(self):
        if not self.is_new():
            frappe.throw(_("Offer Action Log entries are immutable and cannot be updated."), frappe.ValidationError)

    def on_trash(self):
        user = frappe.session.user
        if user != "Administrator":
            frappe.throw(_("Offer Action Log entries cannot be deleted for audit compliance."), frappe.ValidationError)

    def before_insert(self):
        # Ensure timestamp and user are always set correctly
        self.timestamp = frappe.utils.now_datetime()
        self.performed_by = frappe.session.user
