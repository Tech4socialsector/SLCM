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
            "reservation_category": ", ".join([c.category for c in doc.category if c.category]) if doc.category else "General",
            "hsc_percentage": doc.hsc_percentage,
            "entrance_test_score": doc.entrance_test_score,
            "interview_score": doc.interview_score,
            "ug_cgpa": round(ug_avg, 2),
            "pg_cgpa": round(pg_avg, 2)
        })

    if not results:
        # Check if any data is published even without Eligibility Result
        app_id = frappe.db.get_value("Applicant", {"email": user_email}, "name")
        if not app_id:
             app_id = frappe.db.get_value("Applicant", {"owner": user_email}, "name")

        if not app_id:
            return {"error": "No admission application record found for this account."}

        # Check for published Merit List or Seat Allocation
        merit_exists = frappe.db.exists("Merit List Applicant", {"applicant_id": app_id})
        allocation_exists = frappe.db.exists("Seat Selection Applicant", {"applicant_id": app_id})
        
        # If neither exists, then it's truly in progress
        if not merit_exists and not allocation_exists:
            # Check if any scholarship is published to allow early application
            scholarship_available = frappe.db.get_single_value("Admission Settings", "is_scholarship_available")
            if not scholarship_available:
                return {"error": "Your application is under review. Merit lists and scholarships will be visible here once published."}


    # 2. For each result, get the specific selection statuses from Seat Allocation child tables
    settings = frappe.get_single("Admission Settings")
    
    combined_data = []

    # If results is empty but we have an app_id, we might want to synthesize a result
    if not results and app_id:
        app = frappe.get_doc("Applicant", app_id)
        results.append({
            "applicant_id": app_id,
            "candidate_name": app.candidate_name,
            "campus": app.campus,
            "program": app.program,
            "admission_cycle": app.admission_cycle,
            "program_level": app.program_level,
            "reservation_category": ", ".join([c.category for c in app.categories if c.category]) if app.categories else "General",
            "hsc_percentage": getattr(app, "hsc_percentage", 0),
            "entrance_test_score": getattr(app, "entrance_test_score", None),
            "interview_score": getattr(app, "interview_score", None),
            "ug_cgpa": 0,
            "pg_cgpa": 0
        })

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
