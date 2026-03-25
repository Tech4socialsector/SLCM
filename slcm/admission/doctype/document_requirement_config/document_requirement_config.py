import frappe
from frappe.model.document import Document

class DocumentRequirementConfig(Document):

    def validate(self):
        if not self.document_requirements:
            frappe.throw("At least one document requirement must be defined.")
        codes = [d.document_code for d in self.document_requirements if d.document_code]
        if len(codes) != len(set(codes)):
            frappe.throw("Document codes must be unique within a config.")
        for d in self.document_requirements:
            if d.allowed_formats:
                formats = [f.strip().lower() for f in d.allowed_formats.split(",")]
                valid = {"pdf", "jpg", "jpeg", "png", "doc", "docx", "xls", "xlsx"}
                invalid = [f for f in formats if f not in valid]
                if invalid:
                    frappe.throw(
                        f"Invalid format(s) in '{d.document_name}': {', '.join(invalid)}. "
                        f"Allowed: pdf, jpg, jpeg, png, doc, docx, xls, xlsx"
                    )
            if d.max_size_mb and d.max_size_mb > 10:
                frappe.throw(
                    f"Max size for '{d.document_name}' cannot exceed 10 MB."
                )

    @staticmethod
    def get_requirements_for(program, category_code):
        """
        Returns document requirements for a program + category.
        First checks category-specific config, falls back to 'All'.
        Merges both if both exist — category-specific takes priority.
        """
        results = {}
        for cat in [category_code, "All"]:
            config_name = frappe.db.get_value(
                "Document Requirement Config",
                {"program": program, "quota_category": cat, "is_active": 1},
                "name"
            )
            if config_name:
                config = frappe.get_doc("Document Requirement Config", config_name)
                for req in config.document_requirements:
                    if req.document_code not in results:
                        results[req.document_code] = req
        return list(results.values())
