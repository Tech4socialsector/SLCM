import frappe

@frappe.whitelist()
def get_applicant_data():
    """
    Fetches merit scores and admission statuses for the currently logged-in applicant.
    Security: Only returns data matching the session user's email.
    """
    user_email = frappe.session.user
    if user_email == "Guest":
        return {"error": "Unauthorized"}

    # 1. Fetch the primary Applicant records (matching user email)
    # We only care about submitted applications (docstatus=1) for results display
    applicants = frappe.get_all("Applicant", 
        filters={"email": user_email, "docstatus": ["in", [0, 1]]},
        fields=[
            "name", "candidate_name", "campus", "program", 
            "program_level", "admission_cycle",
            "hsc_percentage", "entrance_percentage", "interview_percentage",
            "ug_cgpa", "pg_cgpa"
        ],
        order_by="creation desc"
    )

    if not applicants:
        return {"error": "No applicant record found for this email."}

    combined_data = []
    for app in applicants:
        # In the context of dashboard, we map 'name' to 'applicant_id' and 'candidate_name' to 'applicant_name' 
        # to maintain template compatibility for now.
        profile = app.copy()
        profile.applicant_id = app.name
        profile.applicant_name = app.candidate_name

        # 2. Get specific selection statuses from Seat Allocation child tables
        # Linking to updated 'Seat Selection Applicant' which now links to 'Applicant' DocType
        statuses = frappe.get_all("Seat Selection Applicant",
            filters={"applicant": app.name},
            fields=["selection_status", "overall_rank", "category_rank", "allocation_type", "parent"]
        )
        
        # Inject Seat Allocation details
        for s in statuses:
            if s.parent:
                s.published = frappe.db.get_value("Seat Allocation", s.parent, "status") == "Published"
        
        published_statuses = [s.selection_status for s in statuses if s.published]
        
        available_scholarships = []
        applied_scholarships = []
        
        # Scholarship service expects the Applicant name (APP-...) as applicant_id
        from slcm.admission.utils.scholarship_availability import get_available_scholarships_for_dashboard, get_applied_scholarships_for_dashboard
        available_scholarships = get_available_scholarships_for_dashboard(
            app.name, app.admission_cycle, app.campus, app.program, published_statuses
        )
        applied_scholarships = get_applied_scholarships_for_dashboard(app.name)

        combined_data.append({
            "profile": profile,
            "results": [s for s in statuses if s.published],
            "available_scholarships": available_scholarships,
            "applied_scholarships": applied_scholarships
        })

    return combined_data
