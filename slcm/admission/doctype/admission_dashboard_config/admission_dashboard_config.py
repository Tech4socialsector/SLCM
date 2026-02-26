import frappe
from frappe.model.document import Document
from frappe.utils import now

class AdmissionDashboardConfig(Document):

    @frappe.whitelist()
    def refresh_stats(self):
        cycle = self.admission_cycle
        self.total_applications = frappe.db.count(
            "Applicant", {"admission_cycle": cycle}
        )
        self.submitted_applications = frappe.db.count(
            "Applicant",
            {"admission_cycle": cycle, "application_status": "Submitted"}
        )
        self.under_evaluation = frappe.db.count(
            "Applicant",
            {"admission_cycle": cycle, "application_status": "Under Evaluation"}
        )
        self.shortlisted = frappe.db.count(
            "Applicant",
            {"admission_cycle": cycle, "application_status": "Shortlisted"}
        )
        self.offered = frappe.db.count(
            "Applicant",
            {"admission_cycle": cycle, "application_status": "Offered"}
        )
        self.accepted = frappe.db.count(
            "Applicant",
            {"admission_cycle": cycle, "application_status": "Accepted"}
        )
        self.rejected = frappe.db.count(
            "Applicant",
            {"admission_cycle": cycle, "application_status": "Rejected"}
        )
        self.documents_pending = frappe.db.count(
            "Applicant Document",
            {"is_verified": 0, "docstatus": 1}
        )
        self.last_refreshed = now()
        self.save(ignore_permissions=True)
        frappe.db.commit()
        return {
            "total": self.total_applications,
            "submitted": self.submitted_applications,
            "shortlisted": self.shortlisted,
            "offered": self.offered,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "docs_pending": self.documents_pending
        }