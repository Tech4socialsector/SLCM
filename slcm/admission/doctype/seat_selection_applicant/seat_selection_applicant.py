import frappe
from frappe.model.document import Document

class SeatSelectionApplicant(Document):
	def before_save(self):
		if self.applicant:
			res = frappe.db.get_value("Applicant", self.applicant, ["candidate_name", "name"], as_dict=1)
			if res:
				self.candidate_name = res.candidate_name
				self.applicant_id = res.name
