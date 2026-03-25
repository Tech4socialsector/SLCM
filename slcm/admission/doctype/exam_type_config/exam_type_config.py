import frappe
from frappe.model.document import Document

class ExamTypeConfig(Document):

    def validate(self):
        if self.score_import_method == "API Integration":
            if not self.api_endpoint:
                frappe.throw("API Endpoint is required for API Integration.")
            if not self.api_auth_type:
                frappe.throw("Authentication Type is required for API Integration.")
        if self.score_import_method == "CSV Upload" and self.csv_field_mapping:
            import json
            try:
                json.loads(self.csv_field_mapping)
            except Exception:
                frappe.throw("CSV Field Mapping must be valid JSON.")
        if self.score_fields:
            names = [f.field_name for f in self.score_fields]
            if len(names) != len(set(names)):
                frappe.throw("Score field names must be unique within an exam type.")

    def get_score_field_names(self):
        return [f.field_name for f in self.score_fields]

    def get_primary_score_field(self):
        for f in self.score_fields:
            if f.is_primary_score:
                return f.field_name
        return None
