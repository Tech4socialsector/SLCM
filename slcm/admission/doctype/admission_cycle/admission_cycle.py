import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today

class AdmissionCycle(Document):
    def validate(self):
        self.validate_dates()
        self.validate_workflow_fields()
        self.validate_reservation_matrix()
        self.auto_set_status()

    def validate_dates(self):
        if getdate(self.start_date) >= getdate(self.end_date):
            frappe.throw(
                "Start Date must be before End Date.",
                title="Invalid Date Range"
            )

    def validate_workflow_fields(self):
        if self.workflow_type == "CLAT" and not self.clat_consortium_code:
            frappe.throw(
                "CLAT Consortium Code is mandatory for CLAT workflow.",
                title="Missing Required Field"
            )
        if self.workflow_type == "NLSAT" and not self.nlsat_exam_date:
            frappe.throw(
                "NLSAT Exam Date is mandatory for NLSAT workflow.",
                title="Missing Required Field"
            )

    def validate_reservation_matrix(self):
        if self.reservation_matrix:
            total = sum(row.total_seats for row in self.reservation_matrix)
            if total != self.total_seats:
                frappe.throw(
                    f"Sum of reservation category seats ({total}) "
                    f"must equal Total Seats ({self.total_seats}).",
                    title="Seat Matrix Mismatch"
                )

    def auto_set_status(self):
        today_date = getdate(today())
        if getdate(self.start_date) > today_date:
            self.status = "Draft"
        elif getdate(self.start_date) <= today_date <= getdate(self.end_date):
            self.status = "Active"
        else:
            self.status = "Closed"

    def on_trash(self):
        if frappe.db.exists("Applicant", {"admission_cycle": self.name}):
            frappe.throw(
                "Cannot delete Admission Cycle linked to Applicants.",
                title="Deletion Not Allowed"
            )
