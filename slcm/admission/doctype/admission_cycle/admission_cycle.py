import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime

class AdmissionCycle(Document):

    def validate(self):
        self._validate_exam_type()
        self._validate_date_order()
        self._validate_no_overlap()
        self._validate_rounds()

    def _validate_exam_type(self):
        if not self.exam_type and not self.workflow_type:
            frappe.throw("Exam Type is required. Please select an Exam Type Config.")
        # Auto-migrate workflow_type to exam_type if exam_type blank
        if not self.exam_type and self.workflow_type:
            mapped = frappe.db.get_value(
                "Exam Type Config",
                {"exam_code": self.workflow_type},
                "name"
            )
            if mapped:
                self.exam_type = mapped

    def _validate_date_order(self):
        if self.application_start and self.application_end:
            if get_datetime(self.application_start) >= get_datetime(self.application_end):
                frappe.throw("Application Start must be before Application End.")
        if self.offer_start and self.offer_end:
            if get_datetime(self.offer_start) >= get_datetime(self.offer_end):
                frappe.throw("Offer Start must be before Offer End.")
        if self.evaluation_start and self.evaluation_end:
            if get_datetime(self.evaluation_start) >= get_datetime(self.evaluation_end):
                frappe.throw("Evaluation Start must be before Evaluation End.")
        if self.application_end and self.offer_start:
            if get_datetime(self.offer_start) < get_datetime(self.application_end):
                frappe.throw("Offer window cannot start before Application window ends.")

    def _validate_no_overlap(self):
        if not self.application_start or not self.application_end:
            return
        overlapping = frappe.db.sql("""
            SELECT name FROM `tabAdmission Cycle`
            WHERE admission_year = %s
            AND name != %s
            AND status != 'Closed'
            AND (
                (application_start <= %s AND application_end >= %s)
                OR (application_start <= %s AND application_end >= %s)
                OR (application_start >= %s AND application_end <= %s)
            )
        """, (
            self.admission_year, self.name or "",
            self.application_end, self.application_start,
            self.application_start, self.application_start,
            self.application_start, self.application_end
        ))
        if overlapping:
            frappe.throw(
                f"Application window overlaps with existing cycle "
                f"'{overlapping[0][0]}' in the same Admission Year."
            )

    def _validate_rounds(self):
        if self.have_multiple_rounds and self.rounds:
            priorities = [r.priority for r in self.rounds if r.priority]
            if len(priorities) != len(set(priorities)):
                frappe.throw("Round priority must be unique within a cycle.")
            for r in self.rounds:
                if r.round_start and r.round_end:
                    if get_datetime(r.round_start) >= get_datetime(r.round_end):
                        frappe.throw(f"Round '{r.round_name}': Start must be before End.")

    def before_delete(self):
        applicant_count = frappe.db.count("Applicant", {"admission_cycle": self.name})
        if applicant_count > 0:
            frappe.throw(
                f"Cannot delete cycle '{self.name}'. "
                f"{applicant_count} applicant(s) exist for this cycle."
            )

    def on_update(self):
        if self.status == "Active":
            # Ensure the linked admission year is active
            if not frappe.db.get_value("Admission Year", self.admission_year, "is_active"):
                # Deactivate other years first to maintain single active year enforcement
                frappe.db.sql("""
                    UPDATE `tabAdmission Year`
                    SET is_active = 0
                    WHERE name != %s
                """, (self.admission_year,))
                
                frappe.db.set_value(
                    "Admission Year", self.admission_year, "is_active", 1
                )

    def get_active_programs(self):
        """Returns list of active programs in this cycle."""
        return [p for p in (self.programs or []) if p.is_active]
