import frappe
from frappe.model.document import Document


class EligibilityRule(Document):

    def before_insert(self):
        self.generate_rule_code()

    def generate_rule_code(self):

        if not self.academic_year or not self.campus:
            frappe.throw("Academic Year and Campus are required to generate Rule Code.")

        existing_codes = frappe.get_all(
            "Eligibility Rule",
            filters={
                "academic_year": self.academic_year,
                "campus": self.campus
            },
            pluck="rule_code"
        )

        max_number = 0

        for code in existing_codes:
            if code:
                parts = code.split("-")
                if len(parts) >= 5:  
                    try:
                        number = int(parts[-1])
                        if number > max_number:
                            max_number = number
                    except ValueError:
                        continue

        next_number = max_number + 1
        sequence = str(next_number).zfill(3)
        self.rule_code = f"{self.academic_year}-{self.campus}-ER-{sequence}"
