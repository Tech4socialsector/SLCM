import frappe
import hashlib
from frappe.model.document import Document
from frappe.utils import now
from slcm.admission_managment.utils.regulatory import log_audit_trail

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
