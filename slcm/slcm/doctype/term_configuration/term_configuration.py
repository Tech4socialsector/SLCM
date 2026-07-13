# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class TermConfiguration(Document):
    def validate(self):
        self.validate_dates()

    def validate_dates(self):
        """Validate that end date is after start date"""
        if self.starts and self.ends:
            start_date = getdate(self.starts)
            end_date = getdate(self.ends)

            if end_date <= start_date:
                frappe.throw("End date must be after start date")
