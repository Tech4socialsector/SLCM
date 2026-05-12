# Copyright (c) 2025, TFSS and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _
from frappe.model.document import Document


class StudentParent(Document):
    def validate(self):
        self.validate_aadhaar()
        self.validate_pan()

    def validate_aadhaar(self):
        if self.aadhar and not re.fullmatch(r"\d{12}", str(self.aadhar)):
            frappe.throw(_("Parent Aadhaar Number must be exactly 12 digits."))

    def validate_pan(self):
        if self.pan and not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", str(self.pan).upper()):
            frappe.throw(_("Parent PAN Number format is invalid (e.g. ABCDE1234F)."))
