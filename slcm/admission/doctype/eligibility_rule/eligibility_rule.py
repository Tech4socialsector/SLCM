import frappe
from frappe.model.document import Document


class EligibilityRule(Document):

    def before_insert(self):
        self.generate_rule_code()

    def generate_rule_code(self):

        existing_codes = frappe.get_all(
            "Eligibility Rule",
            pluck="rule_code"
        )

        max_number = 0

        for code in existing_codes:
            if code:
                parts = code.split("-")
                if len(parts) >= 2:  
                    try:
                        number = int(parts[-1])
                        if number > max_number:
                            max_number = number
                    except ValueError:
                        continue

        next_number = max_number + 1
        sequence = str(next_number).zfill(3)
        self.rule_code = f"ER-{sequence}"
