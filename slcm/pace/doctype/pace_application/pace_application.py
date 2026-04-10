# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PACEApplication(Document):
	def validate(self):
		if not self.applicant_name:
			parts = filter(None, [self.get("first_name"), self.get("middle_name"), self.get("last_name")])
			self.applicant_name = " ".join(parts).strip()
			
	def on_submit(self):
		from slcm.pace.doctype.pace_document_verification.get_document_api import generate_document_verification
		generate_document_verification(self.name)
