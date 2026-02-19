import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate

class AdmissionYear(Document):
	def autoname(self):
		self.name = f"AY-{self.academic_year}"

	def validate(self):
		self.validate_dates()
		self.validate_cycles()
		self.validate_status()
		self.validate_one_open_year()
		self.validate_campus_duplicates()
		self.validate_cycles_duplicates()

	def validate_dates(self):
		if getdate(self.application_end_date) <= getdate(self.application_start_date):
			frappe.throw(_("Application End Date must be greater than Application Start Date"))

	def validate_cycles(self):
		if not self.cycles:
			return

		for cycle in self.cycles:
			# Cycle dates must be within admission year dates
			if getdate(cycle.start_date) < getdate(self.application_start_date) or \
			   getdate(cycle.end_date) > getdate(self.application_end_date):
				frappe.throw(_("Cycle {0} dates must be within Admission Year dates ({1} to {2})").format(
					cycle.cycle_name, frappe.utils.format_date(self.application_start_date), frappe.utils.format_date(self.application_end_date)
				))
			
			if getdate(cycle.end_date) <= getdate(cycle.start_date):
				frappe.throw(_("Cycle {0}: End Date must be greater than Start Date").format(cycle.cycle_name))

		# Prevent overlapping cycles
		sorted_cycles = sorted(self.cycles, key=lambda x: x.start_date)
		for i in range(len(sorted_cycles) - 1):
			if getdate(sorted_cycles[i].end_date) >= getdate(sorted_cycles[i+1].start_date):
				frappe.throw(_("Cycles {0} and {1} are overlapping").format(
					sorted_cycles[i].cycle_name, sorted_cycles[i+1].cycle_name
				))

	def validate_status(self):
		if self.status == "Open":
			# Cannot set status = Open if no campus is active
			if not any(c.is_active for c in self.participating_campuses):
				frappe.throw(_("Cannot set status to Open if no campus is active"))

			# Cannot open admission if no program offering exists
			if not frappe.db.exists("Program Offering", {"admission_year": self.name, "is_available_for_admission": 1}):
				frappe.throw(_("Cannot open admission if no Program Offering exists for this year"))

	def validate_one_open_year(self):
		if self.status == "Open":
			existing_open_year = frappe.db.get_value("Admission Year", 
				{"status": "Open", "name": ["!=", self.name]}, "name")
			if existing_open_year:
				frappe.throw(_("Admission Year {0} is already Open. Only one Admission Year can be Open at a time.").format(existing_open_year))

	def validate_campus_duplicates(self):
		if not self.participating_campuses:
			return
		
		campuses = {}
		for row in self.participating_campuses:
			if row.campus in campuses:
				frappe.throw(
					_("Campus {0} Already exist in row {1}. Remove the duplicate entry.".format(row.campus, campuses[row.campus])),
					title="Duplicate Entry")
			campuses[row.campus] = row.idx

	def validate_cycles_duplicates(self):
		if not self.cycles:
			return

		cycles = {}
		for row in self.cycles:
			if row.cycle_name in cycles:
				frappe.throw(
					_("Cycle {0} is already exist in {1}. remove duplicate"
					.format(row.cycle_name, cycles[row.cycle_name])),
					title="Duplicate Entry"
				)
			cycles[row.cycle_name] = row.idx

@frappe.whitelist()
def activate_admission_year(admission_year):

	try:
		if not admission_year:
			return {
				"status": "Error",
				"message": _("Admission Year is required.")
			}

		year = frappe.get_doc("Admission Year", admission_year)

		current_academic_year = frappe.db.get_single_value(
			"Admission Settings",
			"current_academic_year"
		)

		if year.academic_year != current_academic_year:
			return {
				"status": "Error",
				"message": _("Academic Year {0} is not the current academic year.")
				.format(year.academic_year)
			}


		frappe.db.sql("""
			UPDATE `tabAdmission Year`
			SET is_active = 0
			WHERE is_active = 1
			AND name != %s
		""", (admission_year,))

		year.db_set("is_active", 1)

		return {
			"status": "success",
			"message": _("Admission Year {0} has been activated.")
			.format(year.academic_year)
		}

	except frappe.DoesNotExistError:
		return {
			"status": "Error",
			"message": _("Admission Year not found.")
		}

	except frappe.ValidationError as e:
		return {
			"status": "Error",
			"message": str(e)
		}

	except Exception as e:
		frappe.log_error(
			title="Admission Year Activation Error",
			message=frappe.get_traceback()
		)
		return {
			"status": "Error",
			"message": _("Something went wrong while activating the Admission Year.")
		}


