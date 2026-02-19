import frappe
from frappe import _
from frappe.model.document import Document

class ProgramOffering(Document):
	def validate(self):
		self.validate_availability()
		self.sync_with_admission_year()

	def validate_availability(self):
		if self.is_available_for_admission:
			campus = frappe.get_doc("Campus", self.campus)
			admission_year = frappe.get_doc("Admission Year", self.admission_year)

			if not campus.is_active:
				frappe.throw(_("Campus {0} is not active. Cannot enable Program Offering.").format(self.campus))

			if not admission_year.allow_campus_enrollment:
				frappe.throw(_("Admission Year {0} is not allowing campus enrollment. Current status: {1}").format(
					self.admission_year, admission_year.allow_campus_enrollment
				))
			is_participating = any(c.campus == self.campus and c.is_active for c in admission_year.participating_campuses)
			if not is_participating:
				frappe.throw(_("Campus {0} is not a participating active campus for Admission Year {1}").format(
					self.campus, self.admission_year
				))


	def before_save(self):
		if not self.is_available_for_admission and not self.is_new():
			if frappe.db.exists("Student Application", {"program_offering": self.name}):
				frappe.throw(_("Cannot disable Program Offering {0} as applications have already been submitted").format(self.name))

	def on_update(self):
		self.sync_with_admission_year()


	def sync_with_admission_year(self):
		admission_year_name = frappe.db.get_value(
			"Admission Year",
			{"is_active": 1},
			"name"
		)

		if not admission_year_name:
			return

		admission_year = frappe.get_doc("Admission Year", admission_year_name)

		current_academic_year = frappe.db.get_single_value(
			"Admission Settings",
			"current_academic_year"
		)

		if admission_year.academic_year != current_academic_year:
			frappe.throw(
				_("Admission Year {0} is not the current academic year.")
				.format(admission_year.academic_year)
			)

		#  Find existing campus row
		for row in admission_year.participating_campuses:
			if row.campus == self.campus:

				# Update only existing row
				row.eligibility_criteria = self.eligibility_based
				row.entrence_test = self.need_entrence_test
				row.schedule_interview = self.interview_required
				row.merit_list = self.merit_list
				row.offer_scholarship = self.scholarship_applicable
				row.reservation_applied = self.is_reservation_applicable
				row.is_active = self.is_available_for_admission

				admission_year.save()
				break




@frappe.whitelist()
def configuration_settings(admission_year):

	try:
		year = frappe.get_doc(
			"Admission Year",
			admission_year,
			is_active=1,
			fields=[
				"enable_scholarship",
				"enable_interview",
				"enable_reservation"
			]
		)

		return year

	except frappe.DoesNotExistError:
		return {
			"status": "Error",
			"message": _("Admission Year not found.")
		}
	except Exception as e:
		 return{
			"status": "Error",
			"message": _("Something went wrong while fetching configuration settings.")
		 }


# @frappe.whitelist()
# @frappe.validate_and_sanitize_search_inputs
# def get_filtered_reservation_rule(doctype, txt, searchfield, start, page_len, filters):

#     return frappe.db.sql("""
#         SELECT DISTINCT rr.name
#         FROM `tabProgram Offering Criteria` poc
#         INNER JOIN `tabReservation Rule` rr
#             ON rr.name = poc.reservation_rule
#         WHERE poc.program = %(program)s
#         AND poc.campus = %(campus)s
#         AND poc.admission_year = %(admission_year)s
#         AND rr.docstatus < 2
#         AND rr.name LIKE %(txt)s
#         LIMIT %(start)s, %(page_len)s
#     """, {
#         "program": filters.get("program"),
#         "campus": filters.get("campus"),
#         "admission_year": filters.get("admission_year"),
#         "txt": "%" + txt + "%",
#         "start": start,
#         "page_len": page_len
#     })