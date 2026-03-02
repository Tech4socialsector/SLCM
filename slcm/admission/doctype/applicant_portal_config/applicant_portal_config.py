import frappe
from frappe.model.document import Document

class ApplicantPortalConfig(Document):

    def validate(self):
        if not self.primary_color:
            try:
                color = frappe.db.get_single_value("Institution Settings", "portal_theme_color")
                if color:
                    self.primary_color = color
            except Exception:
                self.primary_color = "#1a237e"

    def on_update(self):
        frappe.cache().delete_key("applicant_portal_config")
