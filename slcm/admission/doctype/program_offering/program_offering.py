import frappe
from frappe import _
from frappe.model.document import Document


@frappe.whitelist()
def create_merit_rule(program_offering, admission_cycle, programme_level,
					  rule_name, version, effective_from, effective_to, is_active, components):
	"""Create a Merit Rule and link it to the Program Offering."""
	if isinstance(components, str):
		components = json.loads(components)

	doc = frappe.new_doc("Merit Rule")
	doc.rule_name = rule_name
	doc.admission_cycle = admission_cycle
	doc.program_level = programme_level
	doc.version = int(version or 1)
	doc.effective_from = effective_from
	doc.effective_to = effective_to or None
	doc.is_active = int(is_active or 0)
	doc.approval_authority = "Admissions Committee"

	for comp in components:
		doc.append("components", {
			"component_type": comp.get("component_type"),
			"weight": float(comp.get("weight") or 0),
			"is_active": int(comp.get("is_active") or 1)
		})

	doc.insert(ignore_permissions=True)

	# Link back to the program offering
	frappe.db.set_value("Program Offering", program_offering, "merit_rule", doc.name)

	return doc.name


@frappe.whitelist()
def get_programs_for_matrix(doctype, txt, searchfield, start, page_len, filters):
	"""Returns programs linked to active Program Offerings for the given cycle and campus."""
	if not filters:
		return []
	
	admission_cycle = filters.get("admission_cycle")
	campus = filters.get("campus")
	
	if not admission_cycle or not campus:
		return []

	# Join with Program to get the name/title if needed, but here we just need the program link
	return frappe.db.sql("""
		SELECT DISTINCT program
		FROM `tabProgram Offering`
		WHERE admission_cycle = %s
		AND campus = %s
		AND is_active = 1
		AND program LIKE %s
		ORDER BY program ASC
		LIMIT %s, %s
	""", (admission_cycle, campus, f"%{txt}%", start, page_len))


class ProgramOffering(Document):
	def validate(self):
		self.validate_availability()

	def validate_availability(self):
		if self.is_available_for_admission:
			# Cache campus and admission year
			campus = frappe.get_doc("Campus", self.campus)
			admission_year = frappe.get_doc("Admission Year", self.admission_year)

			# 1. Campus must be active
			if not campus.is_active:
				frappe.throw(_("Campus {0} is not active. Cannot enable Program Offering.").format(self.campus))

			# 2. Admission Year must be Open
				
				frappe.throw(_("Admission Year {0} is not allowing campus enrollment. Current status: {1}").format(
					self.admission_year, admission_year.allow_campus_enrollment
				))
			
			# 3. Campus must be part of Admission Year
			is_participating = any(c.campus == self.campus and c.is_active for c in admission_year.participating_campuses)
			if not is_participating:
				frappe.throw(_("Campus {0} is not a participating active campus for Admission Year {1}").format(
					self.campus, self.admission_year
				))


	def before_save(self):
		# Cannot disable program if applications already submitted
		if not self.is_available_for_admission and not self.is_new():
			# Check if any applications exist for this program offering
			# Assuming Application doctype name is "Student Application" or similar, 
			# but requirements say "Application DocType"
			if frappe.db.exists("Student Application", {"program_offering": self.name}):
				frappe.throw(_("Cannot disable Program Offering {0} as applications have already been submitted").format(self.name))


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


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_filtered_reservation_rule(doctype, txt, searchfield, start, page_len, filters):

    return frappe.db.sql("""
        SELECT DISTINCT rr.name
        FROM `tabProgram Offering Criteria` poc
        INNER JOIN `tabReservation Rule` rr
            ON rr.name = poc.reservation_rule
        WHERE poc.program = %(program)s
        AND poc.campus = %(campus)s
        AND poc.admission_year = %(admission_year)s
        AND rr.docstatus < 2
        AND rr.name LIKE %(txt)s
        LIMIT %(start)s, %(page_len)s
    """, {
        "program": filters.get("program"),
        "campus": filters.get("campus"),
        "admission_year": filters.get("admission_year"),
        "txt": "%" + txt + "%",
        "start": start,
        "page_len": page_len
    })