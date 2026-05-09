import frappe
from frappe.model.document import Document

class ShortlistingProcess(Document):
    def clear_all_lists(self):
        tables = [
            "shortlist_applicants", "master_rank_list", "general_list", 
            "sc_list", "st_list", "obc_list", "ews_list",
            "karnataka_list", "women_list", "pwd_list"
        ]
        for t in tables:
            if self.get(t):
                self.set(t, [])

    def pull_from_merit_list(self, merit):
        if isinstance(merit, str):
            merit = frappe.get_doc("Merit List", merit)
            
        self.clear_all_lists()
        
        for row in merit.merit_applicants:
            self.append("shortlist_applicants", {
                "applicant_id": row.applicant_id,
                "candidate_name": row.candidate_name,
                "program": row.program,
                "nlsat_part_a_score": row.total_score, # Use total_score from Part A Ranking
                "shortlist_rank": row.overall_rank,
                "category_rank": row.category_rank,
                "actual_category": row.get("actual_category"),
                "date_of_birth": row.get("date_of_birth"),
                "shortlist_status": "Shortlisted"
            })
        self.total_candidates = len(self.shortlist_applicants)
        self.total_shortlisted = len([a for a in self.shortlist_applicants if a.shortlist_status == "Shortlisted"])
        
        # Automatically execute shortlisting logic to fill categories
        from slcm.admission.doctype.merit_rule.merit_service import execute_advanced_allocation_logic
        execute_advanced_allocation_logic(self, is_shortlist_allocation=True)
        
        # Re-calculate shortlisted count after allocation
        self.total_shortlisted = len([a for a in self.shortlist_applicants if a.shortlist_status == "Shortlisted"])
        
        self.status = "Allocated"
        self.save()

    @frappe.whitelist()
    def execute_shortlisting_logic(self):
        from slcm.admission.doctype.merit_rule.merit_service import execute_advanced_allocation_logic
        execute_advanced_allocation_logic(self, is_shortlist_allocation=True)
        self.total_shortlisted = len([a for a in self.shortlist_applicants if a.shortlist_status == "Shortlisted"])
        self.status = "Allocated"
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
