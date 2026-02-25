import frappe
from frappe.model.document import Document

class ApplicationFormConfig(Document):
    def validate(self):
        self.validate_no_edit_if_in_use()

    def validate_no_edit_if_in_use(self):
        if not self.is_new():
            submitted = frappe.db.count("Applicant", {
                "admission_cycle": self.admission_cycle,
                "application_status": ["!=", "Draft"]
            })
            if submitted and self.has_value_changed("is_active"):
                frappe.throw(
                    "Cannot modify form config after applications are submitted.",
                    title="Form In Use"
                )

        def before_save(self):
            if not self.is_new():
                self.version = (self.version or 1) + 1
    
        def get_ordered_fields(self):
            """Returns form fields sorted by sequence."""
            return sorted(self.form_fields or [], key=lambda f: f.sequence)
    
