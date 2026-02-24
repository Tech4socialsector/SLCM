import frappe
from frappe.model.document import Document
from slcm.admission_managment.utils.regulatory import (
    log_audit_trail, check_reservation_compliance
)

class CampusSeatMatrix(Document):
    def validate(self):
        if self.is_locked:
            frappe.throw(
                "This Seat Matrix is locked and cannot be modified.",
                title="Matrix Locked"
            )
        self.validate_seats()
        self.validate_reservation_breakdown()
        self.calculate_available_seats()

    def validate_seats(self):
        if self.total_seats <= 0:
            frappe.throw(
                "Total Seats must be greater than 0.",
                title="Invalid Seats"
            )
        if self.filled_seats > self.total_seats:
            frappe.throw(
                f"Filled Seats ({self.filled_seats}) cannot exceed "
                f"Total Seats ({self.total_seats}).",
                title="Seat Overflow"
            )

    def validate_reservation_breakdown(self):
        if self.reservation_breakdown:
            total = sum(row.total_seats for row in self.reservation_breakdown)
            if total != self.total_seats:
                frappe.throw(
                    f"Sum of reservation seats ({total}) must equal "
                    f"Total Seats ({self.total_seats}).",
                    title="Reservation Mismatch"
                )
            for row in self.reservation_breakdown:
                if row.filled_seats > row.total_seats:
                    frappe.throw(
                        f"Filled seats for {row.category} exceed total seats.",
                        title="Category Seat Overflow"
                    )

    def calculate_available_seats(self):
        self.available_seats = self.total_seats - (self.filled_seats or 0)

    def on_submit(self):
        self.db_set("is_locked", 1)
        log_audit_trail(
            self.doctype, self.name,
            "Submitted", "is_locked", 0, 1, "Reservation"
        )
        frappe.msgprint(
            "Seat Matrix submitted and locked. No further edits allowed.",
            indicator="green",
            title="Matrix Locked"
        )

    def on_cancel(self):
        frappe.throw(
            "Seat Matrix cannot be cancelled once submitted.",
            title="Action Not Allowed"
        )
