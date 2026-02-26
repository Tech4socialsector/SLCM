import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime

class AdmissionCycleDeadline(Document):

    def validate(self):
        if get_datetime(self.start_datetime) >= get_datetime(self.end_datetime):
            frappe.throw("Start datetime must be before End datetime.")
        cycle = frappe.get_doc("Admission Cycle", self.admission_cycle)
        if hasattr(cycle, "application_start") and cycle.application_start:
            if get_datetime(self.start_datetime) < get_datetime(cycle.application_start):
                frappe.throw(
                    f"Deadline start ({self.start_datetime}) cannot be before "
                    f"cycle start ({cycle.application_start})."
                )
        if hasattr(cycle, "offer_end") and cycle.offer_end:
            if get_datetime(self.end_datetime) > get_datetime(cycle.offer_end):
                frappe.throw(
                    f"Deadline end ({self.end_datetime}) cannot be after "
                    f"cycle end ({cycle.offer_end})."
                )
        overlapping = frappe.db.exists(
            "Admission Cycle Deadline",
            {
                "admission_cycle": self.admission_cycle,
                "deadline_type": self.deadline_type,
                "name": ("!=", self.name or ""),
                "is_active": 1
            }
        )
        if overlapping:
            frappe.throw(
                f"An active '{self.deadline_type}' deadline already exists for this cycle. "
                f"Deactivate it before creating a new one."
            )
        if cycle.status == "Active":
            if not frappe.has_permission("Admission Cycle Deadline", "write", user=frappe.session.user):
                frappe.throw(
                    "Deadlines cannot be edited after cycle is Active. "
                    "Contact Super Admin for approval."
                )
