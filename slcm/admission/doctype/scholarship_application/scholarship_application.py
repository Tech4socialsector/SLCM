# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
import hashlib
import json
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import now_datetime, flt, get_datetime


class ScholarshipApplication(Document):
	def autoname(self):
		if not self.admission_cycle:
			frappe.throw(frappe._("Admission Cycle is mandatory for naming"))
		
		# Naming Series: SA-{CYCLE}-.#####
		self.name = make_autoname(f"SA-{self.admission_cycle}-.#####")
		
	def validate(self):
		if not self.status:
			self.status = "Draft"
			
		if self.approval_date and get_datetime(self.approval_date) > get_datetime(now_datetime()):
			frappe.throw(frappe._("Approval Date cannot be in the future."))

		# If workflow is active, ensure status and workflow_state are in sync
		if getattr(self, "workflow_state", None):
			self.status = self.workflow_state
		else:
			# Ensure workflow_state is populated for initial record
			self.workflow_state = self.status

		self.set_applicant_metadata()
		self.set_academic_year()
		self.prevent_duplicate()
		self.validate_scheme_mapping()
		self.validate_requirements()
		self.validate_stage()
		self.set_original_fee()
		self.calculate_benefit()
		self.validate_rejection_reason()
		self.validate_approval_authority()
		self.validate_conflicts()

	def set_applicant_metadata(self):
		if not self.applicant_id:
			return

		if not self.applicant_name:
			self.applicant_name = frappe.db.get_value("Applicant", self.applicant_id, "candidate_name")

	def set_academic_year(self):
		if self.admission_cycle and not self.academic_year:
			admission_year = frappe.db.get_value("Admission Cycle", self.admission_cycle, "admission_year")
			if admission_year:
				# Academic Year usually matches Admission Year name in this system
				if frappe.db.exists("Academic Year", admission_year):
					self.academic_year = admission_year
				else:
					# Fallback to Admission Settings
					self.academic_year = frappe.db.get_single_value("Admission Settings", "current_academic_year")

	def set_original_fee(self):
		if not self.applicant_id or not self.program:
			return

		from slcm.api.service.offer_service import OfferService
		from slcm.api.service.fee_service import FeeService

		# Resolve admission year
		campus = self.campus or frappe.db.get_value("Applicant", self.applicant_id, "campus")
		cycle = self.admission_cycle or frappe.db.get_value("Applicant", self.applicant_id, "admission_cycle")
		
		try:
			admission_year = OfferService.resolve_admission_year(self.applicant_id, campus, cycle)
			if not admission_year:
				return

			# Get active config
			config = OfferService.get_active_config(admission_year, cycle, campus)
			
			fee_structure_name = None
			for row in config.fee_structure:
				fs_program = frappe.db.get_value("Fee Structure", row.fee_structure, "program")
				if fs_program == self.program:
					fee_structure_name = row.fee_structure
					break
			
			if fee_structure_name:
				fee_data = FeeService._calculate_and_freeze_fees(fee_structure_name)
				self.original_fee_amount = flt(fee_data.get("total_payable") or 0)
		except Exception:
			# If resolution fails, we don't block save, but fee might be 0
			pass

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
				"campus": self.campus,
				"is_active": 1
			},
			fields=["program", "category"]
		)
		
		is_applicable = False
		from slcm.admission.doctype.seat_allocation.seat_allocation import get_applicant_categories
		applicant_categories = get_applicant_categories(self.applicant_id)
		
		for m in mappings:
			# Check program match (mapping has specific program or is global)
			program_match = not m.program or m.program == self.program
			
			# Check category match (if mapping has category, student must have it in their multi-category list)
			category_match = not m.category or m.category in applicant_categories
			
			if program_match and category_match:
				is_applicable = True
				break

		if not is_applicable:
			frappe.throw(frappe._("Scholarship not applicable or inactive for selected cycle/program/campus/category."))

	def validate_requirements(self):
		# Always mandatory as per user request
		if self.family_income is None or self.family_income == "":
			frappe.throw(frappe._("Family Income is mandatory for this scholarship"))
		if not self.income_certificate:
			frappe.throw(frappe._("Income Certificate is mandatory for this scholarship"))

		scheme = frappe.get_doc("Scholarship Scheme", self.scholarship_scheme)
		
		# 1. Income Validation
		if scheme.scheme_type == "Need" and scheme.income_certificate_required:
			if scheme.max_income and flt(self.family_income) > flt(scheme.max_income):
				frappe.throw(frappe._("Family Income {0} exceeds the maximum allowed {1} for this scholarship")
					.format(self.family_income, scheme.max_income))
			if scheme.min_income and flt(self.family_income) < flt(scheme.min_income):
				frappe.throw(frappe._("Family Income {0} is below the minimum required {1} for this scholarship")
					.format(self.family_income, scheme.min_income))

		# 2. Merit Validation
		if scheme.scheme_type == "Merit" and scheme.min_merit_score:
			# Try to fetch total score from Merit List Applicant
			merit_score = frappe.db.get_value(
				"Merit List Applicant",
				{
					"applicant_id": self.applicant_id,
					"parentfield": "merit_applicants"
				},
				"total_score"
			)
			
			if merit_score is None:
				# Fallback to Eligibility Result entrance percentage
				merit_score = frappe.db.get_value(
					"Eligibility Result",
					{"applicant_id": self.applicant_id, "admission_cycle": self.admission_cycle},
					"entrance_percentage"
				)

			if merit_score is not None:
				if flt(merit_score) < flt(scheme.min_merit_score):
					frappe.throw(frappe._("Your merit score ({0}) is below the required minimum ({1}) for this scholarship")
						.format(merit_score, scheme.min_merit_score))
			else:
				# No merit score found at all
				frappe.msgprint(
					frappe._("Warning: No merit score found for this applicant. Manual verification required for Merit Scholarship."),
					indicator="orange"
				)

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
		
		# 1. Check if applicant already has an APPROVED Exclusive scholarship
		# If they do, they cannot have ANY other scholarship.
		exclusive_exists = frappe.db.exists("Scholarship Application", {
			"applicant_id": self.applicant_id,
			"status": "Approved",
			"name": ["!=", self.name],
			"scholarship_scheme": ["in", frappe.get_all("Scholarship Scheme", filters={"exclusive_scheme": 1}, pluck="name")]
		})
		
		if exclusive_exists:
			frappe.throw(frappe._("Applicant already has an Approved Exclusive scholarship and cannot hold any other schemes."))

		# 2. If THIS scheme is Exclusive, check if they have ANY other Approved scholarship
		if scheme.exclusive_scheme:
			any_approved = frappe.db.exists("Scholarship Application", {
				"applicant_id": self.applicant_id,
				"status": "Approved",
				"name": ["!=", self.name]
			})
			if any_approved:
				frappe.throw(frappe._("This is an Exclusive scholarship. It cannot be approved because the applicant already has another active scholarship."))

		# 3. Check Max Schemes Per Applicant limit from Admission Cycle
		limit = frappe.db.get_value("Admission Cycle", self.admission_cycle, "max_schemes_per_applicant")
		if limit and limit > 0:
			approved_count = frappe.db.count("Scholarship Application", {
				"applicant_id": self.applicant_id,
				"status": "Approved",
				"name": ["!=", self.name],
				"admission_cycle": self.admission_cycle # Limit per cycle
			})
			
			if approved_count >= limit:
				frappe.throw(frappe._("Limit Reached: This admission cycle allows a maximum of {0} approved scholarships per applicant. Applicant already has {1}.").format(limit, approved_count))

	def on_update(self):
		# Sync status from workflow_state if it exists
		if getattr(self, "workflow_state", None) and self.status != self.workflow_state:
			self.db_set("status", self.workflow_state)
		elif self.status and not getattr(self, "workflow_state", None):
			self.db_set("workflow_state", self.status)

		self.create_audit_log()
		
		old_doc = self.get_doc_before_save()
		if not old_doc:
			if self.status == "Approved":
				self.apply_financial_effects()
				self.sync_fee_assignment()
			return

		# Case 1: Status changed from something else to Approved
		if old_doc.status != "Approved" and self.status == "Approved":
			self.apply_financial_effects()
			self.sync_fee_assignment()
		
		# Case 2: Status changed from Approved to something else
		elif old_doc.status == "Approved" and self.status != "Approved":
			self.reverse_financial_effects()
			self.sync_fee_assignment(reverse=True)
		
		# Case 3: Remains Approved but benefit changed
		elif self.status == "Approved" and old_doc.status == "Approved":
			benefit_diff = flt(self.calculated_benefit) - flt(old_doc.calculated_benefit)
			if benefit_diff != 0:
				scheme = frappe.get_doc("Scholarship Scheme", self.scholarship_scheme)
				new_budget = flt(scheme.utilized_budget or 0) + flt(benefit_diff)
				scheme.db_set("utilized_budget", new_budget)
			
			# Always ensure fee deduction is synced if still approved
			self.sync_fee_assignment()

	def on_trash(self):
		if self.status == "Approved":
			self.reverse_financial_effects()
			self.sync_fee_assignment(reverse=True)

	def sync_fee_assignment(self, reverse=False):
		"""
		Updates the linked Applicant Fee Assignment with scholarship benefit.
		Calculates the TOTAL approved scholarship amount for this applicant in this cycle
		to ensure multiple scholarships are handled correctly (cumulative).
		"""
		if not self.applicant_id or not self.admission_cycle:
			return

		# Query matching AFA
		afa_data = frappe.db.get_value("Applicant Fee Assignment", {
			"applicant": self.applicant_id,
			"admission_cycle": self.admission_cycle,
			"docstatus": ["!=", 2]
		}, ["name", "total_amount"], as_dict=True)

		if not afa_data:
			return

		afa_name = afa_data.name
		total_amount = flt(afa_data.total_amount)
		
		# Calculate cumulative scholarship amount from ALL approved applications for this applicant + cycle
		# We use direct SQL to avoid permission issues and ensure we get the latest committed data
		total_scholarship = frappe.db.sql("""
			SELECT SUM(calculated_benefit)
			FROM `tabScholarship Application`
			WHERE applicant_id = %s AND admission_cycle = %s AND status = 'Approved'
		""", (self.applicant_id, self.admission_cycle))[0][0] or 0

		scholarship_applied = 1 if total_scholarship > 0 else 0
		final_payable_amount = total_amount - flt(total_scholarship)
		
		msg = frappe._("Fee Assignment {0} synced. Total Scholarship: {1}, Final Payable: {2}")\
			.format(afa_name, total_scholarship, final_payable_amount)
		indicator = "green"

		# Apply changes directly to DB
		frappe.db.set_value("Applicant Fee Assignment", afa_name, {
			"scholarship_amount": total_scholarship,
			"scholarship_applied": scholarship_applied,
			"final_payable_amount": final_payable_amount
		}, update_modified=True)
		
		frappe.db.commit()
		frappe.msgprint(msg, indicator=indicator)

	def create_audit_log(self):
		"""
		Records status changes and application creation in the Scholarship Audit Log.
		"""
		old_doc = self.get_doc_before_save()
		
		is_new = not old_doc
		if not is_new and old_doc.status == self.status:
			# Only log if status has changed
			return

		# Mapping status to action_type allowed in Scholarship Audit Log
		action_map = {
			"Submitted": "Apply",
			"Under Review": "Review",
			"Approved": "Approve",
			"Rejected": "Reject",
			"Revoked": "Revoke",
			"Cancelled": "Revoke",
			"Draft": "Modify"
		}
		
		# If new and already submitted (e.g. from web form), use Apply
		if is_new:
			action_type = "Apply" if self.status != "Draft" else "Modify"
			previous_state = {}
		else:
			action_type = action_map.get(self.status, "Modify")
			previous_state = old_doc.as_dict()

		# Determine triggered_by based on user role/session
		triggered_by = "Admin"
		if frappe.session.user == self.owner:
			triggered_by = "Applicant"
		elif frappe.session.user == "Administrator":
			triggered_by = "System"

		# Create hash for tamper detection
		record_string = json.dumps({
			"application": self.name,
			"old_status": old_doc.status if old_doc else None,
			"new_status": self.status,
			"user": frappe.session.user,
			"time": str(now_datetime())
		}, sort_keys=True)
		record_hash = hashlib.sha256(record_string.encode()).hexdigest()

		try:
			frappe.get_doc({
				"doctype": "Scholarship Audit Log",
				"scholarship_application": self.name,
				"scholarship_scheme": self.scholarship_scheme,
				"admission_cycle": self.admission_cycle,
				"campus": self.campus,
				"program": self.program,
				"action_type": action_type,
				"previous_state": json.dumps(previous_state, indent=4, default=str),
				"new_state": json.dumps(self.as_dict(), indent=4, default=str),
				"performed_by": frappe.session.user,
				"triggered_by": triggered_by,
				"action_timestamp": now_datetime(),
				"reason": self.rejection_reason or f"Status changed to {self.status}",
				"ip_address": frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None,
				"record_hash": record_hash
			}).insert(ignore_permissions=True)
		except Exception as e:
			# Log to Error Log but don't stop the main Scholarship save
			frappe.log_error(title="Scholarship Audit Log Error", message=frappe.get_traceback())

	def apply_financial_effects(self):
		scheme = frappe.get_doc("Scholarship Scheme", self.scholarship_scheme)
		approved_amt = self.calculated_benefit or 0

		new_beneficiaries = (scheme.current_beneficiaries or 0) + 1
		new_budget = flt(scheme.utilized_budget or 0) + flt(approved_amt)
		new_status = scheme.status

		# Auto-archive logic
		if scheme.max_beneficiaries and new_beneficiaries >= scheme.max_beneficiaries:
			new_status = "Archived"

		if scheme.total_budget and new_budget >= scheme.total_budget:
			new_status = "Archived"

		scheme.db_set({
			"current_beneficiaries": new_beneficiaries,
			"utilized_budget": new_budget,
			"status": new_status
		})

	def reverse_financial_effects(self):
		scheme = frappe.get_doc("Scholarship Scheme", self.scholarship_scheme)
		old_doc = self.get_doc_before_save()
		approved_amt = 0
		if old_doc:
			approved_amt = old_doc.calculated_benefit or 0
		else:
			approved_amt = self.calculated_benefit or 0

		new_beneficiaries = max(0, (scheme.current_beneficiaries or 0) - 1)
		new_budget = max(0, flt(scheme.utilized_budget or 0) - flt(approved_amt))
		new_status = scheme.status

		# Re-activate logic: if it was archived and now we are below limits
		if scheme.status == "Archived":
			bene_ok = not scheme.max_beneficiaries or new_beneficiaries < scheme.max_beneficiaries
			budget_ok = not scheme.total_budget or new_budget < scheme.total_budget
			if bene_ok and budget_ok:
				new_status = "Active"

		scheme.db_set({
			"current_beneficiaries": new_beneficiaries,
			"utilized_budget": new_budget,
			"status": new_status
		})

@frappe.whitelist()
def create_scholarship_application(scheme, family_income, income_certificate_data=None, income_certificate_name=None, supporting_documents_data=None, supporting_documents_name=None):
	"""
	Creates a new Scholarship Application from the portal dashboard with support for base64 files.
	"""
	user = frappe.session.user
	frappe.log_error(f"Applying for scheme {scheme} by user {user}", "Scholarship Application Debug")
	
	if user == "Guest" or not user:
		frappe.throw(frappe._("You must be logged in to apply for a scholarship."))

	# Get applicant record
	applicant = frappe.db.get_value("Applicant", {"email": user}, 
		["name", "candidate_name", "program", "campus", "admission_cycle"], as_dict=1)
	
	if not applicant:
		# Fallback 1: check Eligibility Result if Applicant email doesn't match
		applicant_id = frappe.db.get_value("Eligibility Result", {"email": user}, "applicant_id")
		if applicant_id:
			applicant = frappe.db.get_value("Applicant", applicant_id, 
				["name", "candidate_name", "program", "campus", "admission_cycle"], as_dict=1)
	
	if not applicant:
		# Fallback 2: search by owner (User ID)
		applicant = frappe.db.get_value("Applicant", {"owner": user}, 
			["name", "candidate_name", "program", "campus", "admission_cycle"], as_dict=1)

	if not applicant:
		frappe.log_error(f"No applicant found for user {user}", "Scholarship Application Debug")
		frappe.throw(frappe._("No applicant record found for your account."))

	frappe.log_error(f"Found applicant {applicant.name}", "Scholarship Application Debug")

	# Handle file uploads
	income_cert_url = None
	if income_certificate_data and income_certificate_name:
		try:
			from frappe.utils.file_manager import save_file
			import base64
			
			if "," in income_certificate_data:
				income_certificate_data = income_certificate_data.split(",")[1]
				
			file_content = base64.b64decode(income_certificate_data)
			# Save file without attachment initially to avoid name mandatory error
			saved_file = save_file(income_certificate_name, file_content, None, None, is_private=0)
			income_cert_url = saved_file.file_url
		except Exception as e:
			frappe.log_error(f"File upload error (Income): {e}", "Scholarship Application Debug")
			frappe.throw(frappe._("Failed to upload Income Certificate: {0}").format(str(e)))

	supporting_docs_url = None
	if supporting_documents_data and supporting_documents_name:
		try:
			from frappe.utils.file_manager import save_file
			import base64
			
			if "," in supporting_documents_data:
				supporting_documents_data = supporting_documents_data.split(",")[1]
				
			file_content = base64.b64decode(supporting_documents_data)
			# Save file without attachment initially to avoid name mandatory error
			saved_file = save_file(supporting_documents_name, file_content, None, None, is_private=0)
			supporting_docs_url = saved_file.file_url
		except Exception as e:
			frappe.log_error(f"File upload error (Supporting): {e}", "Scholarship Application Debug")

	# Create the application
	try:
		app = frappe.get_doc({
			"doctype": "Scholarship Application",
			"applicant_id": applicant.name,
			"applicant_name": applicant.candidate_name,
			"admission_cycle": applicant.admission_cycle,
			"campus": applicant.campus,
			"program": applicant.program,
			"scholarship_scheme": scheme,
			"family_income": flt(family_income),
			"income_certificate": income_cert_url,
			"supporting_documents": supporting_docs_url,
			"status": "Submitted"
		})
		
		app.insert(ignore_permissions=True)
		
		# Update file references
		if income_cert_url:
			frappe.db.set_value("File", {"file_url": income_cert_url}, {
				"attached_to_doctype": "Scholarship Application",
				"attached_to_name": app.name
			}, update_modified=False)
		if supporting_docs_url:
			frappe.db.set_value("File", {"file_url": supporting_docs_url}, {
				"attached_to_doctype": "Scholarship Application",
				"attached_to_name": app.name
			}, update_modified=False)
			
		frappe.db.commit()
		return app.name
	except Exception as e:
		frappe.log_error(f"Insert error: {e}", "Scholarship Application Debug")
		frappe.throw(str(e))

@frappe.whitelist()
def get_calculated_benefit(doc):
	if isinstance(doc, str):
		doc = frappe._dict(json.loads(doc))
	
	from slcm.admission.utils.scholarship_coverage_engine import calculate_scholarship_amount
	
	benefit = calculate_scholarship_amount(doc)
	final_fee = flt(doc.original_fee_amount or 0) - flt(benefit or 0)
	
	return {
		"benefit": benefit,
		"final_fee": final_fee
	}

@frappe.whitelist()
def sync_fee_assignment_manually(docname):
	"""
	Whitelisted method to manually trigger fee assignment sync from Client Script.
	"""
	doc = frappe.get_doc("Scholarship Application", docname)
	if doc.status == "Approved":
		doc.sync_fee_assignment()
	else:
		frappe.throw(frappe._("Fee assignment can only be synced for Approved applications."))

@frappe.whitelist()
def get_original_fee_amount(applicant_id, program, campus=None, cycle=None):
	"""
	Whitelisted method for JS access to fetch original fee amount.
	"""
	if not applicant_id or not program:
		return 0

	from slcm.api.service.offer_service import OfferService
	from slcm.api.service.fee_service import FeeService

	# Resolve missing fields from Applicant
	if not campus or not cycle:
		details = frappe.db.get_value("Applicant", applicant_id, ["campus", "admission_cycle"], as_dict=1)
		if details:
			campus = campus or details.campus
			cycle = cycle or details.admission_cycle

	if not campus or not cycle:
		return 0

	try:
		admission_year = OfferService.resolve_admission_year(applicant_id, campus, cycle)
		if not admission_year:
			return 0

		config = OfferService.get_active_config(admission_year, cycle, campus)
		
		fee_structure_name = None
		for row in config.fee_structure:
			fs_program = frappe.db.get_value("Fee Structure", row.fee_structure, "program")
			if fs_program == program:
				fee_structure_name = row.fee_structure
				break
		
		if fee_structure_name:
			fee_data = FeeService._calculate_and_freeze_fees(fee_structure_name)
			return flt(fee_data.get("total_payable") or 0)
	except Exception:
		pass
	
	return 0


@frappe.whitelist()
def get_applicant_details():
	"""Returns the applicant record for the current user based on session email."""
	user = frappe.session.user
	if user == "Guest" or not user:
		return None
	
	applicant = frappe.db.get_value("Applicant", {"email": user}, 
		["name", "candidate_name", "program", "campus", "admission_cycle"], as_dict=1)
	return applicant


@frappe.whitelist()
def get_eligible_scholarship_schemes(applicant_id, program, campus, admission_cycle):
	"""Returns a list of eligible scholarship schemes for the applicant."""
	if not all([applicant_id, program, campus, admission_cycle]):
		return []

	mappings = frappe.get_all(
		"Scholarship Scheme Mapping",
		filters={
			"admission_cycle": admission_cycle,
			"campus": campus
		},
		fields=["scholarship_scheme", "program", "category"]
	)
	
	applicant_categories = frappe.get_all("Applicant Category", filters={"parent": applicant_id}, fields=["category"])
	applicant_category_names = [c.category for c in applicant_categories]
	
	eligible_schemes = []
	for m in mappings:
		# Check program match (mapping has specific program or is global)
		program_match = not m.program or m.program == program
		
		# Check category match (mapping has specific category or is global)
		category_match = not m.category or m.category in applicant_category_names
		
		if program_match and category_match:
			scheme_status = frappe.db.get_value("Scholarship Scheme", m.scholarship_scheme, "status")
			if scheme_status == "Active":
				eligible_schemes.append(m.scholarship_scheme)
				
	return list(set(eligible_schemes))
