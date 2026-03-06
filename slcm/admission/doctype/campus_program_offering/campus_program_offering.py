import frappe
from frappe.model.document import Document

class CampusProgramOffering(Document):
    def validate(self):
        self.validate_duplicate()
        self.validate_intake()
        self.validate_cycle_workflow()

    def validate_duplicate(self):
        existing = frappe.db.exists("Campus Program Offering", {
            "campus": self.campus,
            "program": self.program,
            "admission_cycle": self.admission_cycle,
            "name": ["!=", self.name]
        })
        if existing:
            frappe.throw(
                f"An offering for <b>{self.program}</b> at <b>{self.campus}</b> "
                f"already exists for this cycle.",
                title="Duplicate Offering"
            )

    def validate_intake(self):
        if self.max_intake <= 0:
            frappe.throw(
                "Max Intake must be greater than 0.",
                title="Invalid Intake"
            )

    def validate_cycle_workflow(self):
        # Look up exam_type from the Admission Cycle Program child table for this program
        cycle_exam_type = frappe.db.get_value(
            "Admission Cycle Program",
            {"parent": self.admission_cycle, "program": self.program},
            "exam_type"
        )
        if cycle_exam_type and cycle_exam_type != self.workflow_type:
            frappe.throw(
                f"Workflow Type must match the Admission Cycle exam type: "
                f"<b>{cycle_exam_type}</b>",
                title="Workflow Mismatch"
            )