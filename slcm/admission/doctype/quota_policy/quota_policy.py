import frappe
from frappe.model.document import Document

class QuotaPolicy(Document):

    def validate(self):
        if not self.quota_entries:
            frappe.throw("At least one quota category is required.")
        codes = [e.category_code for e in self.quota_entries if e.category_code]
        if len(codes) != len(set(codes)):
            frappe.throw("Category codes must be unique within a policy.")
        total = sum(e.mandated_percentage or 0 for e in self.quota_entries)
        if total > 100:
            frappe.throw(
                f"Total mandated percentage is {total}%. Cannot exceed 100%."
            )

    def on_submit(self):
        if self.is_legal_mandate:
            frappe.msgprint(
                "This policy is legally mandated and is now permanently locked.",
                indicator="orange"
            )

    def on_cancel(self):
        if self.is_legal_mandate:
            frappe.throw(
                "Legally mandated policies cannot be cancelled. "
                "Contact System Manager if this is an error."
            )

    def before_delete(self):
        if self.docstatus == 1:
            frappe.throw("Cannot delete a submitted Quota Policy.")
