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

	# def validate(self):
		# self.set_admission_cycle_type_for_single()
		# self.validate_dates()
		# self.validate_unique_year_cycle_type()
		# self.validate_one_active_per_cycle_type()
		# self.validate_campus_duplicates()
		# self.validate_status()
		# self.validate_one_open_year()

	# def set_admission_cycle_type_for_single(self):
	# 	"""If multi_cycle is off, force Regular cycle type."""
	# 	if not self.multi_cycle:
	# 		self.admission_cycle_type = "Regular"

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

	# def validate_unique_year_cycle_type(self):
	# 	existing = frappe.db.get_value(
	# 		"Admission Year",
	# 		{
	# 			"academic_year": self.academic_year,
	# 			"admission_cycle_type": self.admission_cycle_type,
	# 			"name": ["!=", self.name]
	# 		},
	# 		"name"
	# 	)
	# 	if existing:
	# 		frappe.throw(
	# 			_("An Admission Year for Academic Year '{0}' with Cycle Type '{1}' already exists: {2}")
	# 			.format(self.academic_year, self.admission_cycle_type, existing)
	# 		)

	# def validate_one_active_per_cycle_type(self):
	# 	if self.is_active:
	# 		existing = frappe.db.get_value(
	# 			"Admission Year",
	# 			{
	# 				"admission_cycle_type": self.admission_cycle_type,
	# 				"is_active": 1,
	# 				"name": ["!=", self.name]
	# 			},
	# 			"name"
	# 		)
	# 		if existing:
	# 			frappe.throw(
	# 				_("Another Admission Year ({0}) is already active for Cycle Type '{1}'. Only one can be active at a time.")
	# 				.format(existing, self.admission_cycle_type)
	# 			)

	def validate_status(self):
		if self.status == "Active":
			if not any(c.is_active for c in (self.participating_campuses or [])):
				frappe.msgprint(
					_("Warning: No active participating campus found for this Admission Year."),
					alert=True
				)

	def validate_one_open_year(self):
		if self.status == "Active":
			existing_open_year = frappe.db.get_value(
				"Admission Year",
				{"status": "Active", "name": ["!=", self.name]},
				"name"
			)
			if existing_open_year:
				frappe.throw(
					_("Admission Year {0} is already Active. Only one Admission Year can be Active at a time.")
					.format(existing_open_year)
				)

	def validate_campus_duplicates(self):
		if not self.participating_campuses:
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
			WHERE is_active = 1 AND name != %s
		""", (admission_year,))

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
