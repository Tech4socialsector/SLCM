import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


STAGE_CONFIG_FIELDS = [
	"enable_entrance_test",
	"enable_interview",
	"enable_document_verification",
	"enable_merit_list",
	"enable_scholarship",
]

AUDITED_FIELDS = [
	"start_date", "end_date", "status", "is_active",
	"enable_entrance_test", "enable_interview",
	"enable_document_verification", "enable_merit_list",
	"enable_scholarship",
]


class AdmissionCycle(Document):

	def autoname(self):
		self.name = "AC-{0}-{1}".format(self.admission_year, self.cycle_code)

	def validate(self):
		self.validate_admission_year_active_for_status()
		self.validate_unique_active_per_year_level()
		self.validate_cycle_dates_within_year()
		self.validate_deadline_windows()
		self.validate_cross_cycle_overlap()
		self.validate_stage_sequence()
		self.validate_stage_date_ranges()
		self.validate_rules()
		self.validate_auto_lock()
		self.validate_lock_enforcement()
		self.validate_change_reason_post_activation()

	def validate_admission_year_active_for_status(self):
		if self.status == "Active":
			ay_active = frappe.db.get_value("Admission Year", self.admission_year, "is_active")
			if not ay_active:
				frappe.throw(
					_("Admission Year '{0}' must be Active before this Admission Cycle can be set to Active.")
					.format(self.admission_year)
				)

	def validate_unique_active_per_year_level(self):
		if not self.is_active:
			return
		existing = frappe.db.get_value(
			"Admission Cycle",
			{
				"admission_year": self.admission_year,
				"programme_level": self.programme_level,
				"is_active": 1,
				"name": ["!=", self.name],
				"docstatus": ["!=", 2],
			},
			"name"
		)
		if existing:
			frappe.throw(
				_("An active Admission Cycle ({0}) already exists for Admission Year '{1}' and Programme Level '{2}'.")
				.format(existing, self.admission_year, self.programme_level)
			)

	def validate_cycle_dates_within_year(self):
		if not self.admission_year:
			return
		ay = frappe.get_doc("Admission Year", self.admission_year)
		ay_start = ay.start_date
		ay_end = ay.end_date
		if not ay_start or not ay_end:
			return
		if self.start_date and getdate(self.start_date) < getdate(ay_start):
			frappe.throw(
				_("Cycle Start Date ({0}) must be on or after the Admission Year start date ({1}).")
				.format(self.start_date, ay_start)
			)
		if self.end_date and getdate(self.end_date) > getdate(ay_end):
			frappe.throw(
				_("Cycle End Date ({0}) must be on or before the Admission Year end date ({1}).")
				.format(self.end_date, ay_end)
			)
		if self.start_date and self.end_date and getdate(self.end_date) <= getdate(self.start_date):
			frappe.throw(_("Cycle End Date must be after Cycle Start Date."))

	def validate_deadline_windows(self):
		"""Validate that specific deadline windows fall within cycle dates."""
		windows = [
			("offer_start_date", "offer_end_date", "Offer Window"),
			("payment_start_date", "payment_end_date", "Payment Window"),
		]
		for start_f, end_f, label in windows:
			s_val = self.get(start_f)
			e_val = self.get(end_f)
			if s_val and e_val:
				if getdate(e_val) <= getdate(s_val):
					frappe.throw(_("{0}: End Date must be after Start Date.").format(label))
				if self.start_date and getdate(s_val) < getdate(self.start_date):
					frappe.throw(_("{0}: Start Date must be on or after Cycle Start Date ({1}).").format(label, self.start_date))
				if self.end_date and getdate(e_val) > getdate(self.end_date):
					frappe.throw(_("{0}: End Date must be on or before Cycle End Date ({1}).").format(label, self.end_date))

	def validate_cross_cycle_overlap(self):
		"""Prevents overlapping cycles within the same year and programme level."""
		if not (self.admission_year and self.programme_level and self.start_date and self.end_date):
			return
		
		# Check for overlapping date ranges
		overlapping = frappe.db.sql("""
			SELECT name FROM `tabAdmission Cycle`
			WHERE admission_year = %s 
			AND programme_level = %s
			AND name != %s
			AND docstatus < 2
			AND (
				(start_date <= %s AND end_date >= %s) OR
				(start_date <= %s AND end_date >= %s) OR
				(%s <= start_date AND %s >= start_date)
			)
		""", (self.admission_year, self.programme_level, self.name, 
			self.start_date, self.start_date, self.end_date, self.end_date, 
			self.start_date, self.end_date), as_dict=1)

		if overlapping:
			frappe.throw(_("This cycle overlaps with another Admission Cycle: {0}").format(overlapping[0].name))

	def validate_change_reason_post_activation(self):
		"""Requires a reason for change for critical fields after the cycle is Active."""
		if self.is_new():
			return
		
		old = self.get_doc_before_save()
		if not old or old.status == "Draft":
			return
		
		critical_fields = ["status", "start_date", "end_date", "is_active", "offer_start_date", "offer_end_date", "payment_start_date", "payment_end_date"]
		changed = [f for f in critical_fields if str(self.get(f)) != str(old.get(f))]
		
		if changed and not getattr(self, "lock_override_reason", None):
			frappe.throw(_("Please provide a 'Lock Override Reason' for changing critical fields ({0}) after the cycle is no longer in Draft.").format(", ".join(changed)))

	def validate_stage_sequence(self):
		if not self.stages:
			return
		# Check unique sequence_no
		seen_seq = {}
		for row in self.stages:
			if row.sequence_no in seen_seq:
				frappe.throw(
					_("Duplicate Sequence No {0} in stages (rows {1} and {2}). Sequence must be unique.")
					.format(row.sequence_no, seen_seq[row.sequence_no], row.idx)
				)
			seen_seq[row.sequence_no] = row.idx
		# Check continuous from 1
		sorted_seqs = sorted(seen_seq.keys())
		expected = list(range(1, len(sorted_seqs) + 1))
		if sorted_seqs != expected:
			frappe.throw(
				_("Stage Sequence Numbers must be continuous starting from 1 with no gaps. Found: {0}")
				.format(sorted_seqs)
			)

	def validate_stage_date_ranges(self):
		if not self.stages:
			return
		sorted_stages = sorted(self.stages, key=lambda x: x.sequence_no)
		for row in sorted_stages:
			if not row.start_date or not row.end_date:
				continue
			if getdate(row.end_date) < getdate(row.start_date):
				frappe.throw(
					_("Stage '{0}' (Row {1}): End Date must be on or after Start Date.")
					.format(row.stage_name, row.idx)
				)
			if self.start_date and getdate(row.start_date) < getdate(self.start_date):
				frappe.throw(
					_("Stage '{0}' (Row {1}): Start Date must be within Cycle start date ({2}).")
					.format(row.stage_name, row.idx, self.start_date)
				)
			if self.end_date and getdate(row.end_date) > getdate(self.end_date):
				frappe.throw(
					_("Stage '{0}' (Row {1}): End Date must be within Cycle end date ({2}).")
					.format(row.stage_name, row.idx, self.end_date)
				)
		# Check overlapping stage date ranges
		for i, s1 in enumerate(sorted_stages):
			for j, s2 in enumerate(sorted_stages):
				if i >= j:
					continue
				if not s1.start_date or not s1.end_date or not s2.start_date or not s2.end_date:
					continue
				if getdate(s1.start_date) <= getdate(s2.end_date) and getdate(s2.start_date) <= getdate(s1.end_date):
					frappe.throw(
						_("Stage '{0}' (Row {1}) and Stage '{2}' (Row {3}) have overlapping date ranges.")
						.format(s1.stage_name, s1.idx, s2.stage_name, s2.idx)
					)

	def validate_rules(self):
		if not self.rules:
			return
		seen_types = {}
		for row in self.rules:
			if row.rule_type in seen_types:
				frappe.throw(
					_("Rule Type '{0}' is duplicated in Rules (rows {1} and {2}). Each rule type must be unique per cycle.")
					.format(row.rule_type, seen_types[row.rule_type], row.idx)
				)
			seen_types[row.rule_type] = row.idx
			# Specific value validations
			if row.rule_type == "Offer Validity Days":
				try:
					v = int(row.rule_value)
					if v <= 0:
						raise ValueError
				except (ValueError, TypeError):
					frappe.throw(_("Rule 'Offer Validity Days' must have a positive integer value."))
			elif row.rule_type == "Max Campus Preferences":
				try:
					v = int(row.rule_value)
					if v < 1 or v > 10:
						raise ValueError
				except (ValueError, TypeError):
					frappe.throw(_("Rule 'Max Campus Preferences' must be a positive integer between 1 and 10."))
			elif row.rule_type == "Submission Cutoff":
				try:
					getdate(row.rule_value)
				except Exception:
					frappe.throw(_("Rule 'Submission Cutoff' must have a valid date as its value."))

	def validate_lock_enforcement(self):
		if not self.stage_locked or self.is_new():
			return
		old = self.get_doc_before_save()
		if not old:
			return
		changed_config = [f for f in STAGE_CONFIG_FIELDS if self.get(f) != old.get(f)]
		if changed_config:
			# Check if System Administrator
			current_user = frappe.session.user
			is_sys_admin = "System Manager" in frappe.get_roles(current_user)
			if not is_sys_admin:
				frappe.throw(
					_("Admission Cycle is locked. Stage configuration fields {0} cannot be changed by non-administrators.")
					.format(changed_config)
				)
			else:
				if not self.lock_override_reason:
					frappe.throw(
						_("Admission Cycle is locked. Please provide a 'Lock Override Reason' before changing stage configuration.")
					)
		
	def validate_auto_lock(self):
		"""Automatically set stage_locked if cycle is active or has applications."""
		if self.stage_locked:
			return
		
		# Lock if Active or Closed
		if self.status in ["Active", "Closed"]:
			self.stage_locked = 1
			return

		# Lock if applications exist
		if frappe.db.exists("Applicant", {"admission_cycle": self.name}):
			self.stage_locked = 1


	def after_insert(self):
		"""Copy stage config flags from Admission Year and lock the parent year."""
		if not self.admission_year:
			return
		try:
			ay = frappe.get_doc("Admission Year", self.admission_year)
		except frappe.DoesNotExistError:
			return


		# Lock parent Admission Year
		frappe.db.set_value("Admission Year", self.admission_year, "stage_locked", 1)

	def on_update(self):
		"""Write audit log for every changed audited field."""
		if self.is_new():
			return
		old = self.get_doc_before_save()
		if not old:
			return

		changed_config = [f for f in STAGE_CONFIG_FIELDS if self.get(f) != old.get(f)]
		is_sys_admin = "System Manager" in frappe.get_roles(frappe.session.user)

		for field in AUDITED_FIELDS:
			old_val = old.get(field)
			new_val = self.get(field)
			if str(old_val) == str(new_val):
				continue

			if field in STAGE_CONFIG_FIELDS:
				change_type = "Stage Config Change"
				reason = getattr(self, 'lock_override_reason', '') if (self.stage_locked and is_sys_admin) else ""
			elif field in ("start_date", "end_date"):
				change_type = "Deadline Change"
				reason = ""
			elif field in ("status", "is_active"):
				change_type = "Status Change"
				reason = ""
			else:
				change_type = "Rule Change"
				reason = ""

			log = frappe.new_doc("Admission Cycle Audit Log")
			log.admission_cycle = self.name
			log.changed_field = field
			log.previous_value = str(old_val) if old_val is not None else ""
			log.new_value = str(new_val) if new_val is not None else ""
			log.changed_by = frappe.session.user
			log.change_timestamp = now_datetime()
			log.change_type = change_type
			log.reason = reason
			log.insert(ignore_permissions=True)

		# Lock override audit entry
		lock_override_reason = getattr(self, 'lock_override_reason', '')
		if self.stage_locked and is_sys_admin and changed_config and lock_override_reason:
			log = frappe.new_doc("Admission Cycle Audit Log")
			log.admission_cycle = self.name
			log.changed_field = "lock_override"
			log.previous_value = "locked"
			log.new_value = str(changed_config)
			log.changed_by = frappe.session.user
			log.change_timestamp = now_datetime()
			log.change_type = "Lock Override"
			log.reason = lock_override_reason
			log.insert(ignore_permissions=True)

	def on_submit(self):
		self.db_set("status", "Active")
		self.db_set("is_active", 1)
		self.db_set("stage_locked", 1)

	def on_trash(self):
		if self.status == "Active":
			frappe.throw(_("Cannot delete an Active Admission Cycle. Change its status first."))
		if frappe.db.exists("Admission Application", {"admission_cycle": self.name}):
			frappe.throw(
				_("Cannot delete Admission Cycle '{0}' as Admission Applications are linked to it.")
				.format(self.name)
			)
