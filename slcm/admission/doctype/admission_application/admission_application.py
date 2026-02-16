import frappe
from frappe import _
from frappe.model.document import Document

class AdmissionApplication(Document):
	def validate(self):
		self.validate_admission_status()
		self.validate_program_availability()
		self.set_initial_stage()

	def validate_admission_status(self):
		# Admission Year status != Open → prevent application submission
		admission_year_status = frappe.db.get_value("Admission Year", self.admission_year, "status")
		if admission_year_status != "Open":
			frappe.throw(_("Admission for year {0} is currently {1}. Submissions are not allowed.").format(
				self.admission_year, admission_year_status
			))

	def validate_program_availability(self):
		program = frappe.get_doc("Program Offering", self.program_offering)
		
		# 1. Check if program is available for admission
		if not program.is_available_for_admission:
			frappe.throw(_("Program {0} is not available for admission.").format(program.program_name))

		# 2. Check intake capacity
		current_apps = frappe.db.count("Admission Application", {
			"program_offering": self.program_offering,
			"workflow_state": ["not in", ["Rejected"]] # Only count non-rejected applications
		})
		if current_apps >= program.intake_capacity:
			frappe.throw(_("Intake capacity for {0} is full.").format(program.program_name))

	def set_initial_stage(self):
		if not self.current_stage:
			# Load the first mandatory stage as default
			first_stage = frappe.db.get_value("Stage Master", 
				{"is_mandatory": 1}, "name", order_by="sequence_number asc")
			self.current_stage = first_stage

	@frappe.whitelist()
	def get_applicable_stages(self):
		"""
		Returns stages based on Admission Year and Program configuration.
		"""
		admission_year = frappe.get_doc("Admission Year", self.admission_year)
		program = frappe.get_doc("Program Offering", self.program_offering)

		stages = frappe.get_all("Stage Master", 
			fields=["name", "stage_name", "sequence_number", "is_mandatory", "applicable_for_scholarship", "applicable_for_interview"],
			order_by="sequence_number asc")

		filtered_stages = []
		for stage in stages:
			# Skip interview stages if not enabled in Admission Year OR Program
			if stage.applicable_for_interview and (not admission_year.enable_interview or not program.interview_required):
				continue
			
			# Skip scholarship stages if not enabled in Admission Year OR Program
			if stage.applicable_for_scholarship and (not admission_year.enable_scholarship or not program.scholarship_applicable):
				continue
			
			filtered_stages.append(stage)

		return filtered_stages

@frappe.whitelist()
def get_available_campuses(admission_year):
	"""
	Portal filtering logic: show only active campuses for selected Admission Year
	"""
	campuses = frappe.get_all("Participating Campus", 
		filters={"parent": admission_year, "is_active": 1},
		fields=["campus"])
	return [c.campus for c in campuses]

@frappe.whitelist()
def get_available_programs(admission_year, campus):
	"""
	Portal filtering logic: show only programs available for campus and year
	"""
	programs = frappe.get_all("Program Offering",
		filters={
			"admission_year": admission_year,
			"campus": campus,
			"is_available_for_admission": 1
		},
		fields=["name", "program_name", "intake_capacity"])
	
	# Further filter out programs where intake is filled
	available_programs = []
	for p in programs:
		current_count = frappe.db.count("Admission Application", {
			"program_offering": p.name,
			"workflow_state": ["not in", ["Rejected"]]
		})
		if current_count < p.intake_capacity:
			available_programs.append(p)
			
	return available_programs
