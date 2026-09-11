# Copyright (c) 2025, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FeeComponent(Document):
	pass


DEFAULT_FEE_COMPONENTS = [
	{"component_name": "Admission Fee", "component_type": "Admission Fee", "ledger": "Admission Fee Receivable"},
	{"component_name": "Tuition and Facilities Fee", "component_type": "Tuition and Facilities Fee", "ledger": "Tuition and Facilities Fee Receivable"},
	{"component_name": "Hostel Residential and Mess Charges", "component_type": "Housing and Mess Fee", "ledger": "Hostel Residential and Mess Charges Receivable"},
	{"component_name": "Student Refundable Deposit", "component_type": "Student Refundable Deposit", "ledger": "Student Refundable Deposit"},
	{"component_name": "Deferral Fee", "component_type": "Gap Year Fee", "ledger": "Gap Year Fee"},
	{"component_name": "Re-admission Fee", "component_type": "Re-admission Fee", "ledger": "Readmn Fee Receivable"},
	{"component_name": "Fine - Mobile Phone, Other Disciplinary Things", "component_type": "Fine - Disciplinary", "ledger": "Fine-Mobile Phone,Other Disciplinary Things"},
	{"component_name": "Reregistration Tuition Fee", "component_type": "Re-registration Tuition Fee", "ledger": "Reregistration Tuition Fee Receivable"},
	{"component_name": "Mess Charges - Others", "component_type": "Mess Charges", "ledger": "Mess Charges - Lunch"},
	{"component_name": "Continuation / Extension Fee", "component_type": "Continuation Fee (PhD)", "ledger": "Continuation Fee - Regular Programmes"},
	{"component_name": "Fines - Regular Programmes", "component_type": "Fine - Late Payment", "ledger": "Fines - Regular Programmes"},
	{"component_name": "Convocation Fee", "component_type": "Convocation Fee", "ledger": "Convocation Fee - Regular Programmes"},
	{"component_name": "Application Fee", "component_type": "Application Fee", "ledger": "Application Fee - Regular Programmes"},
	{"component_name": "Final Presentation Fee", "component_type": "Examination Fee", "ledger": "Examination Fee - Regular Programmes"},
	{"component_name": "Examination Fee", "component_type": "Examination Fee", "ledger": "Examination Fee - Regular Programmes"},
	{"component_name": "Re-submission of thesis", "component_type": "Examination Fee", "ledger": "Examination Fee - Regular Programmes"},
	{"component_name": "Annual Fee", "component_type": "Annual Fee (PhD)", "ledger": "Annual Fee Receivable"},
	{"component_name": "Course Work Fee", "component_type": "Course Work Fee (PhD)", "ledger": "Course Work Fee"},
	{"component_name": "Registration Fee", "component_type": "Registration Fee (PhD)", "ledger": "Registration Fee"},
	{"component_name": "Electric Applicance Usage Charges", "component_type": "Electrical Appliance Charges", "ledger": "Electricity & Power Charges"},
	{"component_name": "Laundry Charges", "component_type": "Laundry Charges", "ledger": "Laundry Charges Hostel"},
	{"component_name": "Postage Charges", "component_type": "Other", "ledger": "Postage Charges"},
	{"component_name": "Duplicate ID Card", "component_type": "ID Card Fee", "ledger": "ID Cards Receipts - Regular Programmes"},
	{"component_name": "Provisional Transcript", "component_type": "Provisional Degree Certificate", "ledger": "Provisional Degree Certificate - Regular Programmes"},
]


@frappe.whitelist()
def create_default_fee_components():
	"""Create the standard set of Fee Components (with their Zoho ledger names) if missing."""
	frappe.only_for("System Manager")

	created = []
	skipped = []

	for row in DEFAULT_FEE_COMPONENTS:
		if frappe.db.exists("Fee Component", row["component_name"]):
			skipped.append(row["component_name"])
			continue

		doc = frappe.new_doc("Fee Component")
		doc.update(row)
		doc.insert(ignore_permissions=True)
		created.append(row["component_name"])

	return {"created": created, "skipped": skipped}
