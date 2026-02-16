import frappe
from frappe import _
from frappe.model.document import Document

class OfferFeeSnapshot(Document):
    def validate(self):
        self.validate_unique_per_offer()

    def validate_unique_per_offer(self):
        """Ensures only one fee snapshot is recorded per Offer Letter."""
        if not self.offer_id:
            return
            
        existing = frappe.db.exists("Offer Fee Snapshot", {
            "offer_id": self.offer_id,
            "name": ["!=", self.name]
        })
        
        if existing:
            frappe.throw(_("A fee snapshot already exists for Offer {0}").format(self.offer_id))
