import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class AdmissionRound(Document):

	def validate(self):
		self.validate_unique_cycle_round_number()
		self.validate_one_active_per_cycle()
		self.validate_dates()
		self.validate_parent_cycle_active_for_submit()

	def validate_unique_cycle_round_number(self):
		existing = frappe.db.get_value(
			"Admission Round",
			{
				"admission_cycle": self.admission_cycle,
				"round_number": self.round_number,
				"name": ["!=", self.name],
				"docstatus": ["!=", 2],
			},
			"name"
		)
		if existing:
			frappe.throw(
				_("Round Number {0} already exists for Admission Cycle '{1}' in record {2}. Round Number must be unique per cycle.")
				.format(self.round_number, self.admission_cycle, existing)
			)

	def validate_one_active_per_cycle(self):
		if not self.is_active:
			return
		existing = frappe.db.get_value(
			"Admission Round",
			{
				"admission_cycle": self.admission_cycle,
				"is_active": 1,
				"name": ["!=", self.name],
				"docstatus": ["!=", 2],
			},
			"name"
		)
		if existing:
			frappe.throw(
				_("Another Admission Round ({0}) is already active for Admission Cycle '{1}'. Only one can be active per cycle.")
				.format(existing, self.admission_cycle)
			)

	def validate_dates(self):
		if not self.start_date or not self.end_date:
			return
		if getdate(self.end_date) <= getdate(self.start_date):
			frappe.throw(_("Round End Date must be after Round Start Date."))

		if self.fee_payment_deadline and getdate(self.fee_payment_deadline) > getdate(self.end_date):
			frappe.throw(_("Fee Payment Deadline must be on or before Round End Date."))

		if self.doc_verification_deadline and getdate(self.doc_verification_deadline) > getdate(self.end_date):
			frappe.throw(_("Document Verification Deadline must be on or before Round End Date."))

		# Validate within parent Admission Cycle dates
		if self.admission_cycle:
			cycle = frappe.get_doc("Admission Cycle", self.admission_cycle)
			if cycle.start_date and getdate(self.start_date) < getdate(cycle.start_date):
				frappe.throw(
					_("Round Start Date ({0}) must be on or after the Admission Cycle start date ({1}).")
					.format(self.start_date, cycle.start_date)
				)
			if cycle.end_date and getdate(self.end_date) > getdate(cycle.end_date):
				frappe.throw(
					_("Round End Date ({0}) must be on or before the Admission Cycle end date ({1}).")
					.format(self.end_date, cycle.end_date)
				)

	def validate_parent_cycle_active_for_submit(self):
		"""Only enforce during actual submit (docstatus = 0 → 1)."""
		# We cannot reliably detect submit in validate, so we check
		# only if status is Active (which is set on_submit) — skip here
		pass

	def before_submit(self):
		cycle_status = frappe.db.get_value("Admission Cycle", self.admission_cycle, "status")
		if cycle_status != "Active":
			frappe.throw(
				_("Parent Admission Cycle '{0}' must be Active before this Round can be submitted.")
				.format(self.admission_cycle)
			)

	def on_submit(self):
		self.db_set("status", "Active")
		self.db_set("is_active", 1)

	def on_trash(self):
		if frappe.db.exists("Campus Seat Matrix", {"admission_round": self.name}):
			frappe.throw(
				_("Cannot delete Admission Round '{0}' as it is linked to one or more Campus Seat Matrix records.")
				.format(self.name)
			)
