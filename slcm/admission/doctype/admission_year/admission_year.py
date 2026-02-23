import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


class AdmissionYear(Document):

	def autoname(self):
		if self.academic_year:
			parts = self.academic_year.split("-")
			if len(parts) == 2:
				yr_start = parts[0]
				yr_end = parts[1][-2:]  # last 2 digits of end year
				self.name = f"AY-{yr_start}-{yr_end}"
			else:
				self.name = f"AY-{self.academic_year}"

	def validate(self):
		self.validate_dates()
		self.validate_one_active_per_cycle_type()
		self.validate_campus_duplicates()
		self.validate_status()
		self.validate_one_open_year()
		self.validate_lock_enforcement()


	def validate_dates(self):
		if self.start_date and self.end_date:
			if getdate(self.end_date) <= getdate(self.start_date):
				frappe.throw(_("Admission End Date must be after Admission Start Date."))
		# Check dates fall within linked Academic Year dates
		if self.academic_year and self.start_date and self.end_date:
			ay = frappe.get_doc("Academic Year", self.academic_year)
			if hasattr(ay, "year_start_date") and ay.year_start_date:
				if getdate(self.start_date) < getdate(ay.year_start_date):
					frappe.throw(_("Admission Start Date must be within the Academic Year start date ({0}).").format(ay.year_start_date))
			if hasattr(ay, "year_end_date") and ay.year_end_date:
				if getdate(self.end_date) > getdate(ay.year_end_date):
					frappe.throw(_("Admission End Date must be within the Academic Year end date ({0}).").format(ay.year_end_date))

	def validate_one_active_per_cycle_type(self):
		"""Ensures only one Admission Year is active at a time per cycle type."""
		if self.is_active:
			existing = frappe.db.get_value(
				"Admission Year",
				{
					"is_active": 1,
					"admission_cycle_type": self.admission_cycle_type,
					"name": ["!=", self.name]
				},
				"name"
			)
			if existing:
				frappe.throw(
					_("Another Admission Year ({0}) for cycle type '{1}' is already active. Only one can be active at a time per type.")
					.format(existing, self.admission_cycle_type)
				)

	def validate_status(self):
		if self.status == "Active":
			# Only check participating campuses if the table exists
			campuses = getattr(self, "participating_campuses", [])
			if campuses:
				if not any(c.is_active for c in campuses):
					frappe.msgprint(
						_("Warning: No active participating campus found for this Admission Year."),
						alert=True
					)

	def validate_one_open_year(self):
		if self.status == "Active":
			existing_open_year = frappe.db.get_value(
				"Admission Year",
				{
					"status": "Active", 
					"admission_cycle_type": self.admission_cycle_type,
					"name": ["!=", self.name]
				},
				"name"
			)
			if existing_open_year:
				frappe.throw(
					_("Admission Year {0} for cycle type '{1}' is already Active. Only one Admission Year can be Active at a time per type.")
					.format(existing_open_year, self.admission_cycle_type)
				)

	def validate_lock_enforcement(self):
		if not self.stage_locked or self.is_new():
			return
		old = self.get_doc_before_save()
		if not old:
			return
		
		# Fields to lock
		locked_fields = ["start_date", "end_date", "academic_year", "admission_cycle_type"]
		changed = [f for f in locked_fields if str(self.get(f)) != str(old.get(f))]
		
		if changed:
			is_sys_admin = "System Manager" in frappe.get_roles(frappe.session.user)
			if not is_sys_admin:
				frappe.throw(
					_("Admission Year is locked. Fields {0} cannot be changed.")
					.format(", ".join(changed))
				)

	def validate_campus_duplicates(self):
		if not hasattr(self, "participating_campuses") or not self.participating_campuses:
			return
		seen = {}
		for row in self.participating_campuses:
			if row.campus in seen:
				frappe.throw(
					_("Campus '{0}' is duplicated in Participating Campuses (row {1} and {2}). Remove the duplicate.")
					.format(row.campus, seen[row.campus], row.idx),
					title=_("Duplicate Entry")
				)
			seen[row.campus] = row.idx

	def on_update(self):
		"""Write audit log for every changed audited field."""
		if self.is_new():
			return
		old = self.get_doc_before_save()
		if not old:
			return

		audited_fields = {
			"start_date": "Date Change",
			"end_date": "Date Change",
			"status": "Status Change",
			"is_active": "Activation Change"
		}

		for field, change_type in audited_fields.items():
			old_val = old.get(field)
			new_val = self.get(field)
			
			if str(old_val) == str(new_val):
				continue

			log = frappe.new_doc("Admission Year Audit Log")
			log.admission_year = self.name
			log.changed_field = field
			log.previous_value = str(old_val) if old_val is not None else ""
			log.new_value = str(new_val) if new_val is not None else ""
			log.changed_by = frappe.session.user
			log.change_timestamp = now_datetime()
			log.change_type = change_type
			log.reason = getattr(self, "reason", "") 
			log.insert(ignore_permissions=True)

	def on_trash(self):
		if frappe.db.exists("Admission Cycle", {"admission_year": self.name}):
			frappe.throw(
				_("Cannot delete Admission Year '{0}' as one or more Admission Cycles are linked to it.")
				.format(self.name)
			)


@frappe.whitelist()
def activate_admission_year(admission_year):
	try:
		if not admission_year:
			return {"status": "Error", "message": _("Admission Year is required.")}

		year = frappe.get_doc("Admission Year", admission_year)

		current_academic_year = frappe.db.get_single_value(
			"Admission Settings", "current_academic_year"
		)

		if year.academic_year != current_academic_year:
			return {
				"status": "Error",
				"message": _("Academic Year {0} is not the current academic year.").format(year.academic_year)
			}

		frappe.db.sql("""
			UPDATE `tabAdmission Year`
			SET is_active = 0
			WHERE is_active = 1 AND name != %s AND admission_cycle_type = %s
		""", (admission_year, year.admission_cycle_type))

		year.db_set("is_active", 1)

		return {
			"status": "success",
			"message": _("Admission Year {0} has been activated.").format(year.academic_year)
		}

	except frappe.DoesNotExistError:
		return {"status": "Error", "message": _("Admission Year not found.")}
	except frappe.ValidationError as e:
		return {"status": "Error", "message": str(e)}
	except Exception:
		frappe.log_error(title="Admission Year Activation Error", message=frappe.get_traceback())
		return {"status": "Error", "message": _("Something went wrong while activating the Admission Year.")}
