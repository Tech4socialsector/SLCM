import frappe
from frappe.model.document import Document

class GDPRDataRequest(Document):

    def before_save(self):
        if not self.requested_on:
            self.requested_on = frappe.utils.now()

    def on_submit(self):
        self.processed_by = frappe.session.user
        self._append_audit(f"Request submitted by {frappe.session.user}")
        if self.request_type == "Data Export":
            self._process_data_export()
        elif self.request_type == "Right to Erasure":
            self._process_erasure()
        self.resolved_on = frappe.utils.now()
        self.status = "Completed"
        self.save(ignore_permissions=True)

    def on_cancel(self):
        self.status = "Rejected"
        self._append_audit(f"Request cancelled by {frappe.session.user}")

    def _append_audit(self, message):
        timestamp = frappe.utils.now()
        existing = self.audit_trail or ""
        self.audit_trail = f"{existing}\n[{timestamp}] {message}".strip()

    def _process_data_export(self):
        """Export all personal data for this applicant."""
        from slcm.admission.utils.compliance import gdpr_export
        result = gdpr_export(self.applicant)
        self._append_audit(f"Data export completed. Records: {result.get('record_count', 0)}")

    def _process_erasure(self):
        """Anonymise all personal data for this applicant."""
        from slcm.admission.utils.compliance import gdpr_delete
        result = gdpr_delete(self.applicant)
        self._append_audit(f"Data erasure completed. Fields anonymised: {result.get('fields_cleared', 0)}")
