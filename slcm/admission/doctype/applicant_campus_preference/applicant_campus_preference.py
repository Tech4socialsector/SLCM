import frappe
from frappe.model.document import Document
from slcm.admission.utils.regulatory import log_audit_trail

class ApplicantCampusPreference(Document):
    def validate(self):
        self.validate_max_preferences()
        self.validate_unique_preference_order()
        self.validate_unique_campus()
        self.validate_active_offering()
        self.validate_no_change_after_submit()
        self.set_workflow_type()

    def validate_max_preferences(self):
        count = frappe.db.count("Applicant Campus Preference", {
            "applicant": self.applicant,
            "admission_cycle": self.admission_cycle,
            "name": ["!=", self.name]
        })
        if count >= 3:
            frappe.throw(
                "Maximum 3 campus preferences allowed per applicant per cycle.",
                title="Preference Limit Reached"
            )

    def validate_unique_preference_order(self):
        existing = frappe.db.exists("Applicant Campus Preference", {
            "applicant": self.applicant,
            "admission_cycle": self.admission_cycle,
            "preference_order": self.preference_order,
            "name": ["!=", self.name]
        })
        if existing:
            frappe.throw(
                f"Preference Order {self.preference_order} already exists "
                f"for this applicant.",
                title="Duplicate Preference Order"
            )

    def validate_unique_campus(self):
        existing = frappe.db.exists("Applicant Campus Preference", {
            "applicant": self.applicant,
            "admission_cycle": self.admission_cycle,
            "campus": self.campus,
            "name": ["!=", self.name]
        })
        if existing:
            frappe.throw(
                f"Campus <b>{self.campus}</b> is already added as a preference.",
                title="Duplicate Campus"
            )

    def validate_active_offering(self):
        offering = frappe.db.exists("Campus Program Offering", {
            "campus": self.campus,
            "program": self.program,
            "admission_cycle": self.admission_cycle,
            "is_active": 1
        })
        if not offering:
            frappe.throw(
                f"No active offering found for <b>{self.program}</b> "
                f"at <b>{self.campus}</b> in this cycle.",
                title="No Active Offering"
            )

    def validate_no_change_after_submit(self):
        applicant_status = frappe.db.get_value(
            "Applicant", self.applicant, "application_status"
        )
        if applicant_status not in ["Draft", None]:
            if not frappe.has_permission("Applicant Campus Preference", "write",
                                         raise_exception=False):
                frappe.throw(
                    "Cannot modify campus preference after application is submitted.",
                    title="Preference Locked"
                )

    def set_workflow_type(self):
        # Look up exam_type from the Admission Cycle Program child table for this program
        workflow = frappe.db.get_value(
            "Admission Cycle Program",
            {"parent": self.admission_cycle, "program": self.program},
            "exam_type"
        )
        if workflow:
            self.workflow_type = workflow

    def on_update(self):
        log_audit_trail(
            self.doctype, self.name,
            "Modified", "status",
            None, self.status, "General"
        )