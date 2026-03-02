import frappe
from frappe.model.document import Document


class ProgramMedia(Document):
    def on_update(self):
        frappe.cache().delete_key("portal_program_media")
        frappe.cache().delete_key(f"program_media_{self.program}")
