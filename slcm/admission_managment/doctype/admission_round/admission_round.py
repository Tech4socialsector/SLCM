import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime

class AdmissionRound(Document):
    def validate(self):
        self.validate_dates()
        self.validate_unique_round_number()
        self.validate_cycle_status()
        self.auto_set_status()

    def validate_dates(self):
        if get_datetime(self.application_start) >= get_datetime(self.application_end):
            frappe.throw(
                "Application Start must be before Application End.",
                title="Invalid Date Range"
            )

    def validate_unique_round_number(self):
        existing = frappe.db.exists("Admission Round", {
            "admission_cycle": self.admission_cycle,
            "round_number": self.round_number,
            "name": ["!=", self.name]
        })
        if existing:
            frappe.throw(
                f"Round Number {self.round_number} already exists "
                f"for this Admission Cycle.",
                title="Duplicate Round Number"
            )

    def validate_cycle_status(self):
        cycle_status = frappe.db.get_value(
            "Admission Cycle", self.admission_cycle, "status"
        )
        if cycle_status == "Closed":
            frappe.throw(
                "Cannot create a round for a Closed Admission Cycle.",
                title="Cycle Closed"
            )

    def auto_set_status(self):
        now = now_datetime()
        if get_datetime(self.application_start) > now:
            self.status = "Upcoming"
        elif get_datetime(self.application_start) <= now <= get_datetime(self.application_end):
            self.status = "Active"
        else:
            self.status = "Closed"
