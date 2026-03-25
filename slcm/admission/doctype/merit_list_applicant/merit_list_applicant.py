import frappe
from frappe.model.document import Document

class MeritListApplicant(Document):
	def before_save(self):
		if self.applicant:
			res = frappe.db.get_value("Eligibility Result", self.applicant, ["candidate_name", "applicant_id"], as_dict=1)
			if res:
				self.candidate_name = res.candidate_name
				self.applicant_id = res.applicant_id
