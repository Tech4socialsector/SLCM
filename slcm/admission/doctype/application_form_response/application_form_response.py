import frappe
import json
from frappe.model.document import Document
from frappe.utils import now

class ApplicationFormResponse(Document):

    def before_save(self):
        self.last_saved_on = now()
        if self.responses:
            try:
                json.loads(self.responses)
            except Exception:
                frappe.throw("Responses must be valid JSON.")

    def lock(self):
        self.is_draft = 0
        self.submitted_on = now()
        if self.form_config:
            version = frappe.db.get_value("Application Form Config", self.form_config, "version")
            self.form_version = version or 1
        self.save(ignore_permissions=True)

    def get_responses_dict(self):
        try:
            return json.loads(self.responses or "{}")
        except Exception:
            return {}
