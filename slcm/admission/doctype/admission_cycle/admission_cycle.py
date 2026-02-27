import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now


class AdmissionCycle(Document):

    def validate(self):
        self._validate_single_active_cycle()
        self._validate_dates()
        self._validate_programs()

    def _validate_single_active_cycle(self):
        """Only one cycle can be Active at a time."""
        if self.status == "Active":
            existing = frappe.db.get_value(
                "Admission Cycle",
                {"status": "Active", "name": ("!=", self.name)},
                "cycle_name"
            )
            if existing:
                frappe.throw(
                    f"Cycle <b>{existing}</b> is already Active. "
                    f"Close it before activating this one."
                )

    def _validate_dates(self):
        """Application end must be after start."""
        if self.application_start and self.application_end:
            if get_datetime(self.application_end) <= get_datetime(self.application_start):
                frappe.throw("Application End must be after Application Start.")

    def _validate_programs(self):
        """No duplicate program+campus combination in the same cycle."""
        seen = set()
        for row in (self.programs or []):
            key = (row.program, row.campus or "")
            if key in seen:
                frappe.throw(
                    f"Program <b>{row.program_name or row.program}</b> "
                    f"is added more than once in this cycle."
                )
            seen.add(key)

    def get_active_programs(self):
        """Returns list of active program rows in this cycle."""
        return [p for p in (self.programs or []) if p.is_active]

    def get_stage(self, stage_name):
        """Returns a stage row by name."""
        for s in (self.stages or []):
            if s.stage_name == stage_name:
                return s
        return None
