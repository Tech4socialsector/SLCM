import frappe
from frappe.model.document import Document

class FormConditionRule(Document):
    def validate(self):
        if self.trigger_field == self.target_field:
            frappe.throw(
                "Trigger Field and Target Field cannot be the same.",
                title="Invalid Rule"
            )
        if not self.condition:
            frappe.throw(
                "Condition is mandatory.",
                title="Missing Condition"
            )
        if not self.action:
            frappe.throw(
                "Action is mandatory.",
                title="Missing Action"
            )
        if self.condition in ["=", "!=", ">", "<"] and not self.trigger_value:
            frappe.throw(
                f"Trigger Value is required for condition '{self.condition}'.",
                title="Missing Trigger Value"
            )