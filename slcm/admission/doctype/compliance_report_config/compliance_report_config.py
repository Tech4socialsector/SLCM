import frappe
from frappe.model.document import Document

class ComplianceReportConfig(Document):

    def validate(self):
        # India-only reports cannot be set to International mode
        india_only = ["RTI Response Export", "NAAC Admission Summary", "UGC Compliance Report"]
        intl_only = ["GDPR Personal Data Export", "GDPR Erasure Audit"]

        if self.report_type in india_only and self.compliance_mode == "International":
            frappe.throw(
                f"{self.report_type} is only available in India compliance mode."
            )
        if self.report_type in intl_only and self.compliance_mode == "India":
            frappe.throw(
                f"{self.report_type} is only available in International compliance mode."
            )

    @frappe.whitelist()
    def generate(self):
        """Trigger report generation based on report_type."""
        from slcm.admission.utils.compliance import generate_report
        result = generate_report(self)
        self.last_generated_on = frappe.utils.now()
        self.save(ignore_permissions=True)
        return result

@frappe.whitelist()
def generate_report(report_config):
    doc = frappe.get_doc("Compliance Report Config", report_config)
    return doc.generate()
