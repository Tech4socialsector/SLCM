import frappe
from frappe.model.document import Document

class ShortlistingProcess(Document):
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

    @frappe.whitelist()
    def execute_shortlisting_logic(self):
        from slcm.admission.doctype.merit_rule.merit_service import execute_advanced_allocation_logic
        execute_advanced_allocation_logic(self, is_shortlist_allocation=True)
        self.save()
        frappe.db.commit()

    @frappe.whitelist()
    def generate_final_merit_list(self):
        """
        Triggers the Phase 2 Merit Generation (Entrance + Interview).
        """
        from slcm.admission.doctype.merit_rule.merit_service import generate_merit_for_level
        merit_list = generate_merit_for_level(
            self.admission_cycle, 
            self.campus, 
            self.program_level, 
            processing_stage="Final Allotment Ranking"
        )
        return merit_list.name
