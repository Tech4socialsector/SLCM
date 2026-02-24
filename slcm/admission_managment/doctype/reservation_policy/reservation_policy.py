import frappe
from frappe.model.document import Document

class ReservationPolicy(Document):
    def validate(self):
        if self.is_locked:
            frappe.throw(
                "This Reservation Policy is locked and cannot be modified.",
                title="Locked Record"
            )
        if not 0 <= self.mandated_percentage <= 100:
            frappe.throw(
                "Mandated Percentage must be between 0 and 100.",
                title="Invalid Percentage"
            )
        self.validate_duplicate()

    def validate_duplicate(self):
        existing = frappe.db.exists("Reservation Policy", {
            "academic_year": self.academic_year,
            "program": self.program,
            "category": self.category,
            "name": ["!=", self.name]
        })
        if existing:
            frappe.throw(
                f"A Reservation Policy for <b>{self.category}</b> "
                f"already exists for this Program and Academic Year.",
                title="Duplicate Policy"
            )

    def on_submit(self):
        self.is_locked = 1
        self.db_set("is_locked", 1)
        frappe.msgprint(
            "Reservation Policy is now locked and legally enforced.",
            indicator="green",
            title="Policy Locked"
        )

    def on_cancel(self):
        frappe.throw(
            "Reservation Policy cannot be cancelled once submitted.",
            title="Action Not Allowed"
        )
