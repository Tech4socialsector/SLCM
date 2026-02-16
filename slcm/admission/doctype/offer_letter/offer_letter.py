import frappe
from frappe import _, throw
from frappe.model.document import Document

class OfferLetter(Document):
    def validate(self):
        self.validate_status_transition()
        self.lock_financial_fields()

    def validate_status_transition(self):
        """
        Ensures that status transitions follow the defined lifecycle.
        """
        if self.is_new():
            if not self.offer_status:
                self.offer_status = "Draft"
            return

        # Fetch current status from DB
        db_status = frappe.db.get_value(self.doctype, self.name, "offer_status")
        
        if db_status == self.offer_status:
            return

        # Define allowed transitions
        allowed_transitions = {
            "Draft": ["Issued", "Withdrawn"],
            "Issued": ["Accepted", "Rejected", "Expired", "Withdrawn"],
            "Accepted": ["Withdrawn"], # Only withdrawal possible after acceptance if needed
            "Rejected": [], # Terminal state
            "Expired": ["Issued"], # Allow re-issuing if policy permits, otherwise terminal
            "Withdrawn": ["Draft"] # Allow resetting if withdrawn
        }

        if self.offer_status not in allowed_transitions.get(db_status, []):
            throw(_("Invalid status transition: Cannot change status from {0} to {1}").format(
                db_status, self.offer_status
            ))

    def lock_financial_fields(self):
        """
        Locks financial and Snapshot fields once the offer is Issued or beyond.
        """
        if self.is_new():
            return

        db_status = frappe.db.get_value(self.doctype, self.name, "offer_status")
        
        # If it's already Issued or beyond, we shouldn't allow changing fields that define the offer
        if db_status not in ["Draft"]:
            frozen_fields = [
                "applicant", "campus", "program", "admission_cycle", 
                "offer_configrationn", "payable_amount", "rendered_content",
                "offer_letter_pdf"
            ]
            
            for field in frozen_fields:
                old_val = frappe.db.get_value(self.doctype, self.name, field)
                new_val = self.get(field)
                
                # Compare (handling types)
                if str(old_val) != str(new_val) and field in self.__dict__.get("_unsaved_values", {}):
                     throw(_("Cannot modify {0} after offer has been {1}").format(
                         self.meta.get_label(field), db_status
                     ))
