# Copyright (c) 2026, TFSS and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe import _

class IntegrationTestPACEDocumentVerification(IntegrationTestCase):
	def test_prevent_child_deletion_by_verifier(self):
		# Create a document instance
		doc = frappe.get_doc({
			"doctype": "PACE Document Verification",
			"applicant_name": "Test Applicant",
			"status": "Pending",
			"verification_items": [
				{
					"name": "item_1",
					"document_name": "Class 10 Marksheet",
					"fieldname": "class_10_marksheet",
					"file": "/files/marksheet.pdf",
					"status": "Pending"
				}
			]
		})

		# Mock is_new to return False
		doc.is_new = lambda: False

		# Mock get_roles to return verifier role
		original_get_roles = frappe.get_roles
		frappe.get_roles = lambda *args, **kwargs: ["Document Verifier"]

		# Mock get_doc_before_save to return the old state
		old_doc = frappe.get_doc({
			"doctype": "PACE Document Verification",
			"applicant_name": "Test Applicant",
			"status": "Pending",
			"verification_items": [
				{
					"name": "item_1",
					"document_name": "Class 10 Marksheet",
					"fieldname": "class_10_marksheet",
					"file": "/files/marksheet.pdf",
					"status": "Pending"
				}
			]
		})
		doc.get_doc_before_save = lambda: old_doc

		try:
			# 1. Test when nothing has changed -> should succeed
			doc.prevent_child_deletion_or_modification()

			# 2. Test when file is modified
			doc.verification_items[0].file = "/files/new_marksheet.pdf"
			with self.assertRaises(frappe.ValidationError) as cm:
				doc.prevent_child_deletion_or_modification()
			self.assertIn("You are not allowed to modify or delete the files stored in the child table.", str(cm.exception))

			# Reset file URL
			doc.verification_items[0].file = "/files/marksheet.pdf"

			# 3. Test when child item is deleted
			doc.verification_items = []
			with self.assertRaises(frappe.ValidationError) as cm:
				doc.prevent_child_deletion_or_modification()
			self.assertIn("You are not allowed to delete verification items/files.", str(cm.exception))

			# 4. Test when new item is added
			doc.verification_items = [
				frappe.get_doc({
					"doctype": "PACE Verification Item",
					"name": "item_1",
					"document_name": "Class 10 Marksheet",
					"fieldname": "class_10_marksheet",
					"file": "/files/marksheet.pdf",
					"status": "Pending"
				}),
				frappe.get_doc({
					"doctype": "PACE Verification Item",
					"document_name": "New Document",
					"fieldname": "new_document",
					"file": "/files/new.pdf",
					"status": "Pending"
				})
			]
			with self.assertRaises(frappe.ValidationError) as cm:
				doc.prevent_child_deletion_or_modification()
			self.assertIn("You are not allowed to add new verification items.", str(cm.exception))

		finally:
			# Restore original get_roles
			frappe.get_roles = original_get_roles
