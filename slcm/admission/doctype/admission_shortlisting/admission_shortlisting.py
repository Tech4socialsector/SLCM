import frappe
from frappe.model.document import Document

class AdmissionShortlisting(Document):
    def pull_from_merit_list(self, merit_list_name):
        merit = frappe.get_doc("Merit List", merit_list_name)
        self.shortlist_applicants = []
        
        for row in merit.merit_applicants:
            self.append("shortlist_applicants", {
                "applicant_id": row.applicant_id,
                "candidate_name": row.candidate_name,
                "program": row.program,
                "nlsat_part_a_score": row.entrance_score,
                "shortlist_rank": row.overall_rank,
                "shortlist_status": "Shortlisted"
            })
        self.total_candidates = len(self.shortlist_applicants)
        self.save()

    def execute_shortlisting_logic(self):
        from slcm.admission.doctype.merit_rule.merit_service import execute_advanced_allocation_logic
        # We temporarily adapt the document to the structure expected by the service
        # or we update the service to handle both.
        # For now, let's update the service to be more generic.
        execute_advanced_allocation_logic(self, is_shortlist_allocation=True)
