import frappe
from frappe.model.document import Document
from frappe.utils import now
from slcm.admission_managment.utils.regulatory import log_audit_trail

class MeritList(Document):
    def validate(self):
        if self.is_published:
            frappe.throw(
                "Published Merit List cannot be modified.",
                title="List Locked"
            )
        self.validate_duplicate()

    def validate_duplicate(self):
        existing = frappe.db.exists("Merit List", {
            "admission_cycle": self.admission_cycle,
            "program": self.program,
            "campus": self.campus,
            "round_number": self.round_number,
            "name": ["!=", self.name]
        })
        if existing:
            frappe.throw(
                "A Merit List already exists for this cycle, program, "
                "campus and round.",
                title="Duplicate Merit List"
            )

    def on_submit(self):
        self.db_set("is_published", 1)
        self.db_set("published_on", now())
        self.db_set("published_by", frappe.session.user)
        log_audit_trail(
            self.doctype, self.name,
            "Submitted", "is_published", 0, 1, "Rank"
        )
        frappe.msgprint(
            "Merit List is now published and locked for public viewing.",
            indicator="green",
            title="Merit List Published"
        )

    def on_cancel(self):
        frappe.throw(
            "Published Merit List cannot be cancelled. "
            "This is a legally required record.",
            title="Action Not Allowed"
        )

    def on_trash(self):
        if self.is_published:
            frappe.throw(
                "Cannot delete a published Merit List.",
                title="Deletion Not Allowed"
            )
