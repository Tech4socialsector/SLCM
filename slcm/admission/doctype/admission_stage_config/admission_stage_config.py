import frappe
from frappe.model.document import Document

class AdmissionStageConfig(Document):
    def validate(self):
        if self.is_locked:
            frappe.throw(
                "This Stage is locked and cannot be modified.",
                title="Stage Locked"
            )
        self.validate_unique_sequence()
        self.validate_disable_with_applicants()

    def validate_unique_sequence(self):
        existing = frappe.db.exists("Admission Stage Config", {
            "admission_cycle": self.admission_cycle,
            "sequence": self.sequence,
            "name": ["!=", self.name]
        })
        if existing:
            frappe.throw(
                f"Sequence {self.sequence} already exists for this cycle.",
                title="Duplicate Sequence"
            )

    def validate_disable_with_applicants(self):
        if not self.is_enabled:
            applicants_in_stage = frappe.db.count("Applicant", {
                "admission_cycle": self.admission_cycle,
                "application_status": self.stage_name
            })
            if applicants_in_stage > 0:
                frappe.throw(
                    f"Cannot disable stage <b>{self.stage_name}</b>. "
                    f"{applicants_in_stage} applicant(s) are currently in this stage.",
                    title="Stage Has Applicants"
                )