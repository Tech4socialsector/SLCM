# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
import hashlib
import json
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import now_datetime, flt


class ScholarshipApplication(Document):
	def autoname(self):
		if not self.admission_cycle:
			frappe.throw(frappe._("Admission Cycle is mandatory for naming"))
		
		cycle_code = frappe.db.get_value("Admission Cycle", self.admission_cycle, "cycle_code")
		if not cycle_code:
			frappe.throw(frappe._("Cycle Code not found in Admission Cycle {0}").format(self.admission_cycle))
		
		# Naming Series: SA-{CYCLE}-.#####
		self.name = make_autoname(f"SA-{cycle_code}-.#####")

	def validate(self):
		self.prevent_duplicate()
		self.validate_scheme_mapping()
		self.validate_stage()
		self.calculate_benefit()
		self.validate_rejection_reason()
		self.validate_approval_authority()
		self.validate_conflicts()

	def prevent_duplicate(self):
		existing = frappe.db.exists(
			"Scholarship Application",
			{
				"applicant_id": self.applicant_id,
				"scholarship_scheme": self.scholarship_scheme,
				"status": ["not in", ["Rejected", "Revoked"]],
				"name": ["!=", self.name]
			}
		)

		if existing:
			frappe.throw(frappe._("You have already applied for this scholarship."))

	def validate_scheme_mapping(self):
		mappings = frappe.get_all(
			"Scholarship Scheme Mapping",
			filters={
				"scholarship_scheme": self.scholarship_scheme,
				"admission_cycle": self.admission_cycle,
				"campus": self.campus
			},
			fields=["program", "category"]
		)
		
		is_applicable = False
		applicant_category = getattr(self, "category", None)
		
		for m in mappings:
			# Check program match (mapping has specific program or is global)
			program_match = not m.program or m.program == self.program
			
			# Check category match (mapping has specific category or is global)
			category_match = not m.category or m.category == applicant_category
			
			if program_match and category_match:
				is_applicable = True
				break

		if not is_applicable:
			frappe.throw(frappe._("Scholarship not applicable for selected cycle/program/campus/category."))

	def validate_stage(self):
		# Skip availability checks if rejecting or revoking
		if self.status in ["Rejected", "Revoked"]:
			return
			
		# Skip if already approved and just being updated, to avoid blocking saves on archived schemes
		if not self.is_new():
			old_doc = self.get_doc_before_save()
			if old_doc and old_doc.status == "Approved" and self.status == "Approved":
				return

		from slcm.admission.utils.scholarship_availability import check_scholarship_availability
		
		# Get applicant status
		applicant_status = frappe.db.get_value("Applicant", self.applicant_id, "application_status")
		
		check_scholarship_availability(
			self.scholarship_scheme,
			applicant_status
		)

	def calculate_benefit(self):
		from slcm.admission.utils.scholarship_coverage_engine import calculate_scholarship_amount
		
		self.calculated_benefit = calculate_scholarship_amount(self)
		self.final_fee_amount = flt(self.original_fee_amount or 0) - flt(self.calculated_benefit or 0)

	def validate_rejection_reason(self):
		if self.status == "Rejected" and not self.rejection_reason:
			frappe.throw(frappe._("Rejection reason is mandatory"))

	def validate_approval_authority(self):
		if self.status == "Approved":
			scheme = frappe.get_doc("Scholarship Scheme", self.scholarship_scheme)

			if scheme.approval_authority == "Finance Head":
				if not frappe.has_role("Finance Head"):
					frappe.throw(frappe._("Only Finance Head can approve this scheme"))

			if scheme.approval_authority == "VC":
				if not frappe.has_role("System Manager"):
					frappe.throw(frappe._("Only VC-level authority can approve"))

	def validate_conflicts(self):
		scheme = frappe.get_doc("Scholarship Scheme", self.scholarship_scheme)

		if scheme.exclusive_scheme:
			existing = frappe.db.exists(
				"Scholarship Application",
				{
					"applicant_id": self.applicant_id,
					"status": "Approved",
					"name": ["!=", self.name]
				}
			)

			if existing:
				frappe.throw(frappe._("Applicant already has an approved exclusive scholarship"))

	def on_update(self):
		self.create_audit_log()
		
		old_doc = self.get_doc_before_save()
		if old_doc and old_doc.status == "Approved" and self.status != "Approved":
			self.reverse_financial_effects()
		
		if self.status == "Approved" and (not old_doc or old_doc.status != "Approved"):
			self.apply_financial_effects()

	def on_trash(self):
		if self.status == "Approved":
			self.reverse_financial_effects()

	def create_audit_log(self):
		old_doc = self.get_doc_before_save()
		if not old_doc:
			return

		if old_doc.status == self.status:
			return

		# Create hash for tamper detection
		record_string = json.dumps({
			"application": self.name,
			"old_status": old_doc.status,
			"new_status": self.status,
			"user": frappe.session.user,
			"time": str(now_datetime())
		}, sort_keys=True)

		record_hash = hashlib.sha256(record_string.encode()).hexdigest()

		# Mapping status to action_type if needed
		action_map = {
			"Submitted": "Apply",
			"Under Review": "Review",
			"Approved": "Approve",
			"Rejected": "Reject",
			"Revoked": "Revoke"
		}
		action_type = action_map.get(self.status, self.status)

		frappe.get_doc({
			"doctype": "Scholarship Audit Log",
			"scholarship_application": self.name,
			"scholarship_scheme": self.scholarship_scheme,
			"admission_cycle": self.admission_cycle,
			"campus": self.campus,
			"program": self.program,
			"action_type": action_type,
			"previous_state": json.dumps(old_doc.as_dict(), indent=4, default=str),
			"new_state": json.dumps(self.as_dict(), indent=4, default=str),
			"performed_by": frappe.session.user,
			"triggered_by": "System",
			"action_timestamp": now_datetime(),
			"reason": self.rejection_reason or "Status Change",
			"ip_address": frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None,
			"record_hash": record_hash
		}).insert(ignore_permissions=True)

	def apply_financial_effects(self):
		scheme = frappe.get_doc("Scholarship Scheme", self.scholarship_scheme)
		approved_amt = self.approved_amount or self.calculated_benefit or 0

		scheme.current_beneficiaries += 1
		scheme.utilized_budget += flt(approved_amt)

		# Auto-archive logic
		if scheme.max_beneficiaries and scheme.current_beneficiaries >= scheme.max_beneficiaries:
			scheme.status = "Archived"

		if scheme.total_budget and scheme.utilized_budget >= scheme.total_budget:
			scheme.status = "Archived"

		scheme.save(ignore_permissions=True)

	def reverse_financial_effects(self):
		scheme = frappe.get_doc("Scholarship Scheme", self.scholarship_scheme)
		# We need to know what was the approved amount. 
		# If it's being called from on_update, self.approved_amount might have changed, 
		# but usually it wouldn't change in the same save that changes status from Approved.
		# However, it's safer to use the value from old_doc if available.
		old_doc = self.get_doc_before_save()
		approved_amt = 0
		if old_doc:
			approved_amt = old_doc.approved_amount or old_doc.calculated_benefit or 0
		else:
			approved_amt = self.approved_amount or self.calculated_benefit or 0

		scheme.current_beneficiaries = max(0, scheme.current_beneficiaries - 1)
		scheme.utilized_budget = max(0, scheme.utilized_budget - flt(approved_amt))

		# Re-activate logic: if it was archived and now we are below limits
		if scheme.status == "Archived":
			bene_ok = not scheme.max_beneficiaries or scheme.current_beneficiaries < scheme.max_beneficiaries
			budget_ok = not scheme.total_budget or scheme.utilized_budget < scheme.total_budget
			if bene_ok and budget_ok:
				scheme.status = "Active"

		scheme.save(ignore_permissions=True)
