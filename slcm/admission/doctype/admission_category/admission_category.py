# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document

class AdmissionCategory(Document):
    def autoname(self):
        campus = (self.campus or "MAIN").replace(" ", "")
        category_code = (self.category_code or "GEN").replace(" ", "")

        # Format: CAMPUS-CATEGORY
        self.name = f"{campus}-{category_code}"
