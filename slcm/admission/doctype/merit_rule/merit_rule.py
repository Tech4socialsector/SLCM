import frappe
from frappe.model.document import Document


from frappe.utils import getdate, today


class MeritRule(Document):

    def validate(self):
        self.validate_dates()
        self.validate_total_weight()

    def validate_dates(self):
        if self.effective_from:
            if getdate(self.effective_from) < getdate(today()):
                frappe.throw("Effective From date cannot be in the past")

        if self.effective_from and self.effective_to:
            if getdate(self.effective_to) <= getdate(self.effective_from):
                frappe.throw("Effective To date must be after Effective From date")


    # -----------------------------
    # 1️⃣ Validate Total Weight = 100%
    # -----------------------------
    def validate_total_weight(self):

        if not self.components:
            frappe.throw("Please add at least one Merit Rule Component.")

        total_weight = sum(
            row.weight for row in self.components if row.is_active
        )

        if total_weight != 100:
            frappe.throw(
                f"Total weight must be exactly 100%. Current total: {total_weight}%"
            )
