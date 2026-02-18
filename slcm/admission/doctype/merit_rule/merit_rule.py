import frappe
from frappe.model.document import Document


class MeritRule(Document):

    def validate(self):
        self.validate_total_weight()


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
