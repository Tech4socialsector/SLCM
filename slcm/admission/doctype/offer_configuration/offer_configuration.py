# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class OfferConfiguration(Document):

    def autoname(self):
        """Naming: OC-{Year}-{Cycle}-{Campus}"""
        if self.admission_year and self.admission_cycle and self.campus:
            self.name = f"OC-{self.admission_year}-{self.admission_cycle}-{self.campus}"

    def validate(self):
        if self.is_active:
            self.validate_single_active_config()

    def validate_single_active_config(self):
        existing = frappe.get_all(
            "Offer Configuration",
            filters={
                "admission_year": self.admission_year,
                "admission_cycle": self.admission_cycle,
                "campus": self.campus,
                "is_active": 1,
                "name": ["!=", self.name]
            },
            fields=["name"],
            limit=1
        )

        if existing:
            frappe.throw(
                f"Only one active Offer Configuration is allowed for "
                f"Admission Year : {self.admission_year} - Admission Cycle : {self.admission_cycle} - Campus : {self.campus}"
            )