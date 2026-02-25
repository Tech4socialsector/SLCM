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
@frappe.whitelist()
def sync_applicant_to_admission_result(applicant_name):
    """
    Syncs a single applicant's details to Admission Result.
    Called by Applicant hooks or via bulk sync.
    """
    app = frappe.get_doc("Applicant", applicant_name)
    
    # Only sync for specific statuses if needed, but user said "if i create"
    # Mapping logic
    res_name = frappe.db.get_value("Admission Result", {"applicant_id": app.name})
    
    if res_name:
        res = frappe.get_doc("Admission Result", res_name)
    else:
        res = frappe.new_doc("Admission Result")
        res.applicant_id = app.name

    res.applicant_name = app.candidate_name
    res.email = app.email
    res.campus = app.campus
    res.program = app.program
    res.program_level = app.program_level
    res.reservation_category = app.reservation_category
    res.admission_cycle = app.admission_cycle
    res.hsc_percentage = app.hsc_percentage
    
    res.flags.ignore_mandatory = True
    res.save(ignore_permissions=True)
    return res.name

@frappe.whitelist()
def bulk_sync_from_applicants(admission_cycle, campus, program_level=None):
    """
    Creates Admission Result records for all applicants in a specific cycle and campus.
    """
    filters = {
        "admission_cycle": admission_cycle,
        "campus": campus,
        "application_status": ["in", ["Submitted", "Selected", "Waitlisted", "Offer Issued", "Offer Accepted"]]
    }
    if program_level:
        filters["program_level"] = program_level

    applicants = frappe.get_all("Applicant", filters=filters, fields=["name"])
    
    count = 0
    for app in applicants:
        # Check if result already exists to avoid duplicates if we results are cycle specific
        # (Though current schema keeps applicant_name as unique ID, applicant_id is link)
        if not frappe.db.exists("Admission Result", {"applicant_id": app.name}):
            sync_applicant_to_admission_result(app.name)
            count += 1
        
    frappe.db.commit()
    return count
