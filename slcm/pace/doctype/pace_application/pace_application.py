# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.pdf import get_pdf
from frappe.utils import get_url
import traceback
import time
import random

class PACEApplication(Document):

	def autoname(self):
		from frappe.model.naming import make_autoname
		# Incremental serial number with random-like unique padding
		# Format example: PACE-2024-00001
		self.name = make_autoname(f"PACE-{self.academic_year}-.#####")
		
	def validate(self):
		if not self.applicant_name:
			parts = filter(None, [self.get("first_name"), self.get("middle_name"), self.get("last_name")])
			self.applicant_name = " ".join(parts).strip()
			
	def on_submit(self):
		from slcm.pace.doctype.pace_document_verification.get_document_api import generate_document_verification
		generate_document_verification(self.name)

	def on_update(self):
		self.sync_documents_to_verification()

	def on_update_after_submit(self):
		self.sync_documents_to_verification()

	def sync_documents_to_verification(self):
		"""
		Sync document files to the verification record if they have changed.
		Also add missing document items if they exist on the application.
		"""
		verification_name = frappe.db.get_value("PACE Document Verification", {"application": self.name}, "name")
		if not verification_name:
			return

		verification = frappe.get_doc("PACE Document Verification", verification_name)
		updated = False

		# Identify all document fields from metadata
		meta = frappe.get_meta("PACE Application")
		attach_fields = [
			f for f in meta.fields 
			if f.fieldtype in ["Attach", "Attach Image"] 
			and f.fieldname != "upload_student_photo"
		]

		existing_fieldnames = [row.fieldname for row in verification.verification_items]

		for field in attach_fields:
			current_file = self.get(field.fieldname)
			if not current_file:
				continue

			if field.fieldname in existing_fieldnames:
				# Update existing entry
				for row in verification.verification_items:
					if row.fieldname == field.fieldname:
						if row.file != current_file:
							row.file = current_file
							updated = True
						break
			else:
				# Add missing entry
				verification.append("verification_items", {
					"document_name": field.label,
					"fieldname": field.fieldname,
					"file": current_file,
					"status": "Pending"
				})
				updated = True
		
		if updated:
			verification.save(ignore_permissions=True)
