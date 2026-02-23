import frappe
from frappe.model.document import Document


class AdmissionResult(Document):
	pass

@frappe.whitelist()
def get_applicant_data():
    """
    Fetches merit scores and admission statuses for the currently logged-in applicant.
    Security: Only returns data matching the session user's email.
    """
    user_email = frappe.session.user
    if user_email == "Guest":
        return {"error": "Unauthorized"}

    # 1. Fetch the primary Admission Result records (could be multiple cycles?)
    results = frappe.get_all("Admission Result", 
        filters={"email": user_email},
        fields=[
            "name", "applicant_id", "applicant_name", "campus", "program", 
            "program_level", "reservation_category", "admission_cycle",
            "hsc_percentage", "entrance_percentage", "interview_percentage",
            "ug_cgpa", "pg_cgpa"
        ]
    )

    if not results:
        return {"error": "No applicant record found for this email."}

    # 2. For each result, get the specific selection statuses from Seat Allocation child tables
    # We find 'Seat Selection Applicant' rows that link to this 'Admission Result'
    combined_data = []
    for res in results:
        statuses = frappe.get_all("Seat Selection Applicant",
            filters={"applicant": res.name},
            fields=["selection_status", "overall_rank", "category_rank", "allocation_type", "parent"]
        )
        
        # Inject Seat Allocation details
        for s in statuses:
            if s.parent:
                s.published = frappe.db.get_value("Seat Allocation", s.parent, "status") == "Published"
        
        combined_data.append({
            "profile": res,
            "results": [s for s in statuses if s.published] # Only show published results to applicants
        })

    return combined_data
