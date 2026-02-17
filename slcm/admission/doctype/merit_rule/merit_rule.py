import frappe
from frappe.model.document import Document


class MeritRule(Document):

    def validate(self):

        self.validate_total_weight()
        self.validate_duplicate_active_rule()


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


    # -----------------------------
    # 2️⃣ Prevent Duplicate Active Rule
    # -----------------------------
    def validate_duplicate_active_rule(self):

        if not self.is_active:
            return

        if not self.admission_cycle or not self.program_level:
            frappe.throw("Admission Cycle and Program Level are required for an active rule.")

        existing = frappe.db.exists(
            "Merit Rule",
            {
                "admission_cycle": self.admission_cycle,
                "program_level": self.program_level,
                "is_active": 1,
                "name": ["!=", self.name]
            }
        )

        if existing:
            frappe.throw(
                f"Another active Merit Rule already exists for this "
                "Admission Cycle, Campus and Program Level."
            )
