import frappe
import hashlib
from frappe.model.document import Document
from frappe.utils import now
from slcm.admission.utils.regulatory import log_audit_trail
from slcm.admission.doctype.document_requirement_config.document_requirement_config import DocumentRequirementConfig

class ApplicantDocument(Document):

    def validate(self):
        if self.is_locked:
            frappe.throw(
                "This document is locked and cannot be modified.",
                title="Document Locked"
            )
        if not self.file:
            frappe.throw(
                "File is mandatory.",
                title="Missing File"
            )
        self._validate_against_requirement_config()

    def _validate_against_requirement_config(self):
        """
        Validates uploaded document against Document Requirement Config.
        Checks file format and size if config exists for this program/category.
        """
        if not self.file:
            return
        applicant = frappe.get_doc("Applicant", self.parent)
        program = getattr(applicant, "program", None)
        category = getattr(applicant, "category", "All")
        if not program:
            return
        requirements = DocumentRequirementConfig.get_requirements_for(program, category)
        matched = next(
            (r for r in requirements if r.document_code == self.document_type),
            None
        )
        if not matched:
            return
        # Validate file format
        if matched.allowed_formats and self.file:
            import os
            ext = os.path.splitext(self.file)[1].lower().strip(".")
            allowed = [f.strip().lower() for f in matched.allowed_formats.split(",")]
            if ext not in allowed:
                frappe.throw(
                    f"'{matched.document_name}' must be one of: "
                    f"{matched.allowed_formats.upper()}. "
                    f"You uploaded a .{ext} file.",
                    title="Invalid File Format"
                )
        # Validate file size
        if matched.max_size_mb and self.file:
            try:
                file_doc = frappe.get_doc("File", {"file_url": self.file})
                size_mb = (file_doc.file_size or 0) / (1024 * 1024)
                if size_mb > matched.max_size_mb:
                    frappe.throw(
                        f"'{matched.document_name}' exceeds the maximum size of "
                        f"{matched.max_size_mb} MB. Your file is {size_mb:.1f} MB.",
                        title="File Too Large"
                    )
            except Exception:
                pass

    def before_save(self):
        if self.file:
            self.generate_checksum()

    def generate_checksum(self):
        try:
            file_doc = frappe.get_doc(
                "File", {"file_url": self.file}
            )
            content = file_doc.get_content()
            if isinstance(content, str):
                content = content.encode("utf-8")
            self.checksum = hashlib.sha256(content).hexdigest()
        except Exception as e:
            frappe.log_error(str(e), "Checksum Generation Error")

    def on_submit(self):
        self.db_set("is_locked", 1)
        self.db_set("verified_on", now())
        self.db_set("verified_by", frappe.session.user)
        log_audit_trail(
            self.doctype, self.name,
            "Submitted", "is_locked", 0, 1, "Document"
        )

    def on_cancel(self):
        frappe.throw(
            "Submitted documents cannot be cancelled.",
            title="Action Not Allowed"
        )

    def on_trash(self):
        if self.is_locked:
            frappe.throw(
                "Cannot delete a locked document.",
                title="Deletion Not Allowed"
            )
