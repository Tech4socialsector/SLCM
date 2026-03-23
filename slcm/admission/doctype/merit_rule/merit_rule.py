import frappe
from frappe.model.document import Document


from frappe.utils import getdate, today


class MeritRule(Document):

    def validate(self):
        self.validate_usage()
        self.validate_dates()
        self.validate_total_weight()

    def validate_usage(self):
        """
        Prevent changing the rule if it's already used in a PUBLISHED Merit List.
        Changing the rule would make the existing published results incorrect.
        """
        # 1. Find mappings for this rule
        mappings = frappe.db.get_all(
            "Merit Rule Mapping",
            filters={"merit_rule": self.name},
            fields=["admission_cycle", "campus", "program_level"]
        )
        
        for m in mappings:
            # 2. Check if a published Merit List exists for this mapping
            published_exists = frappe.db.exists("Merit List", {
                "admission_cycle": m.admission_cycle,
                "campus": m.campus,
                "program_level": m.program_level,
                "status": "Published"
            })
            
            if published_exists:
                from frappe.utils import get_link_to_form
                link = get_link_to_form("Merit List", published_exists)
                frappe.throw(
                    f"This Merit Rule cannot be modified because it is currently used by a PUBLISHED Merit List. "
                    f"Unpublish the list first if you need to adjust the calculation logic. "
                    f"<br><br>Linked Published List: {link}",
                    title="Rule in Active Use"
                )

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
