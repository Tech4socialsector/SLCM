import frappe
from frappe.model.document import Document

class InstitutionSettings(Document):

    def validate(self):
        if self.enable_multi_campus and not self.max_campus_preferences:
            self.max_campus_preferences = 3
        if self.support_email:
            from frappe.utils import validate_email_address
            if not validate_email_address(self.support_email):
                frappe.throw("Please enter a valid support email address.")

    def on_update(self):
        frappe.cache().delete_key("institution_settings")
