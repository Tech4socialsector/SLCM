import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class AdmissionRound(Document):

	def validate(self):
		self.validate_unique_cycle_round_number()
		self.validate_one_active_per_cycle()
		self.validate_dates()
		self.validate_no_round_overlap()
		self.validate_parent_cycle_active_for_submit()
		self.validate_auto_lock()
		self.validate_lock_enforcement()

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
	
	def validate_no_round_overlap(self):
		"""Prevents overlapping rounds within the same admission cycle."""
		if not (self.admission_cycle and self.start_date and self.end_date):
			return
		
		# Check for overlapping date ranges
		overlapping = frappe.db.sql("""
			SELECT name FROM `tabAdmission Round`
			WHERE admission_cycle = %s 
			AND name != %s
			AND docstatus < 2
			AND (
				(start_date <= %s AND end_date >= %s) OR
				(start_date <= %s AND end_date >= %s) OR
				(%s <= start_date AND %s >= start_date)
			)
		""", (self.admission_cycle, self.name, 
			self.start_date, self.start_date, self.end_date, self.end_date, 
			self.start_date, self.end_date), as_dict=1)

		if overlapping:
			frappe.throw(_("This round overlaps with another Admission Round: {0}").format(overlapping[0].name))

	def validate_auto_lock(self):
		"""Automatically set stage_locked if round has started."""
		if self.stage_locked:
			return
		
		from frappe.utils import today
		if self.start_date and getdate(today()) >= getdate(self.start_date):
			self.stage_locked = 1

	def validate_lock_enforcement(self):
		if not self.stage_locked or self.is_new():
			return
		old = self.get_doc_before_save()
		if not old:
			return
		
		# Fields to lock
		locked_fields = ["start_date", "end_date", "admission_cycle", "round_number"]
		changed = [f for f in locked_fields if str(self.get(f)) != str(old.get(f))]
		
		if changed:
			is_sys_admin = "System Manager" in frappe.get_roles(frappe.session.user)
			if not is_sys_admin:
				frappe.throw(
					_("Admission Round is locked. Fields {0} cannot be changed.")
					.format(", ".join(changed))
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
		if self.status == "Active":
			frappe.throw(_("Cannot delete an Active Admission Round. Change its status first."))
		
		if self.stage_locked:
			is_sys_admin = "System Manager" in frappe.get_roles(frappe.session.user)
			if not is_sys_admin:
				frappe.throw(_("Cannot delete a locked Admission Round."))
