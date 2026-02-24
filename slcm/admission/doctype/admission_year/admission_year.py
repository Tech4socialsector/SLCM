import frappe
import re
from frappe.model.document import Document

class AdmissionYear(Document):
    def validate(self):
        self.validate_year_format()
        self.validate_single_active_year()

    def validate_year_format(self):
        if not re.match(r'^\d{4}-\d{2}$', self.year):
            frappe.throw(
                "Year format must be YYYY-YY (e.g. 2024-25)",
                title="Invalid Format"
            )
        start = int(self.year[:4])
        end = int(self.year[5:])
        if end != (start + 1) % 100:
            frappe.throw(
                f"Year {self.year} is invalid. End year must follow start year.",
                title="Invalid Year"
            )

    def validate_single_active_year(self):
        if self.is_active:
            existing = frappe.db.get_value(
                "Admission Year",
                {"is_active": 1, "name": ["!=", self.name]},
                "name"
            )
            if existing:
                frappe.throw(
                    f"Admission Year <b>{existing}</b> is already active. "
                    f"Please deactivate it before activating {self.year}.",
                    title="Duplicate Active Year"
                )

    def on_trash(self):
        linked = frappe.db.exists(
            "Admission Cycle",
            {"admission_year": self.name}
        )
        if linked:
            frappe.throw(
                f"Cannot delete Admission Year <b>{self.year}</b>. "
                f"It is linked to one or more Admission Cycles.",
                title="Deletion Not Allowed"
            )