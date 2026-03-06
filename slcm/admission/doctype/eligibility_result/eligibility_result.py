# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EligibilityResult(Document):

    def before_save(self):
        """
        Fetch the Applicant's multi-category child table and populate
        the local `category` table if it is currently empty.
        This mirrors the same pattern used in Entrance Test Seat Allocation
        and Interview Seat Allocation.
        """
        if self.applicant_id and not self.category:
            app_categories = frappe.get_all(
                "Applicant Category",
                filters={"parent": self.applicant_id, "parenttype": "Applicant"},
                fields=["category"]
            )
            for row in app_categories:
                self.append("category", {"category": row.category})

@frappe.whitelist()
def get_applicant_data():
    """
    Fetches merit scores and admission statuses for the currently logged-in applicant.
    Security: Only returns data matching the session user's email.
    """
    user_email = frappe.session.user
    if user_email == "Guest":
        return {"error": "Unauthorized"}

    # 1. Fetch the primary Eligibility Result names first to get full docs
    result_names = frappe.get_all("Eligibility Result", 
        filters={"email": user_email},
        pluck="name"
    )

    results = []
    for name in result_names:
        doc = frappe.get_doc("Eligibility Result", name)
        
        # Calculate averaged UG CGPA
        ug_avg = 0
        if doc.ug_degree_details:
            scores = [float(r.ug_cgpa or r.percentage_cgpa_obtained or 0) for r in doc.ug_degree_details]
            if scores: ug_avg = sum(scores) / len(scores)
            
        # Calculate averaged PG CGPA
        pg_avg = 0
        if doc.pg_degree_details:
            scores = [float(r.pg_cgpa or r.percentagecgpa_obtained or 0) for r in doc.pg_degree_details]
            if scores: pg_avg = sum(scores) / len(scores)

        results.append({
            "name": doc.name,
            "applicant_id": doc.applicant_id,
            "candidate_name": doc.candidate_name,
            "campus": doc.campus,
            "program": doc.program,
            "program_level": doc.program_level,
            "admission_cycle": doc.admission_cycle,
            "reservation_category": doc.reservation_category,
            "hsc_percentage": doc.hsc_percentage,
            "entrance_test_score": doc.entrance_test_score,
            "interview_score": doc.interview_score,
            "ug_cgpa": round(ug_avg, 2),
            "pg_cgpa": round(pg_avg, 2)
        })

    if not results:
        # Check if Applicant record exists to provide a specific message
        app_exists = frappe.db.exists("Applicant", {"email": user_email})
        if not app_exists:
            # Try owner fallback
            app_exists = frappe.db.exists("Applicant", {"owner": user_email})

        if app_exists:
            return {"error": "Your Merit List evaluation is in progress. The results have not been published yet. Please check back later."}
        else:
            return {"error": "No admission application record found for this account."}

    # 2. For each result, get the specific selection statuses from Seat Allocation child tables
    settings = frappe.get_single("Admission Settings")
    
    combined_data = []
    for res in results:
        # Fetch Merit List Entries
        merit_entries = []
        if settings.is_merit_list:
            merit_entries = frappe.get_all("Merit List Applicant",
                filters={"applicant_id": res['applicant_id']},
                fields=["total_score", "overall_rank", "program_rank", "status", "parent"]
            )
            for m in merit_entries:
                if m.parent:
                    m.published = frappe.db.get_value("Merit List", m.parent, "status") == "Published"
        
        # Fetch Seat Allocation Statuses
        statuses = frappe.get_all("Seat Selection Applicant",
            filters={"applicant_id": res['applicant_id']},
            fields=["selection_status", "overall_rank", "allocation_type", "parent", "total_score"]
        )
        
        # Inject Seat Allocation details
        for s in statuses:
            if s.parent:
                s.published = frappe.db.get_value("Seat Allocation", s.parent, "status") == "Published"
        
        published_statuses = [s.selection_status for s in statuses if s.published]
        
        available_scholarships = []
        applied_scholarships = []
        if res['applicant_id'] and settings.is_scholarship_available:
            from slcm.admission.utils.scholarship_availability import get_available_scholarships_for_dashboard, get_applied_scholarships_for_dashboard
            available_scholarships = get_available_scholarships_for_dashboard(
                res['applicant_id'], res['admission_cycle'], res['campus'], res['program'], published_statuses
            )
            applied_scholarships = get_applied_scholarships_for_dashboard(res['applicant_id'])

        combined_data.append({
            "profile": res,
            "merit": [m for m in merit_entries if m.published],
            "results": [s for s in statuses if s.published],
            "available_scholarships": available_scholarships,
            "applied_scholarships": applied_scholarships
        })

    return combined_data
