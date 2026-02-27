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
            "program_level", "admission_cycle",
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
    
    sync_data = {
        "applicant_name": app.candidate_name,
        "email": app.email,
        "campus": app.campus,
        "program": app.program,
        "program_level": app.program_level,
        "admission_cycle": app.admission_cycle,
        "hsc_percentage": app.hsc_percentage
    }

    # Load existing Admission Result
    res_name = frappe.db.get_value("Admission Result", {"applicant_id": app.name})
    if res_name:
        res = frappe.get_doc("Admission Result", res_name)
    else:
        res = frappe.new_doc("Admission Result")
        res.applicant_id = app.name

    # Check for changes in main fields
    has_changes = False
    for field, value in sync_data.items():
        if res.get(field) != value:
            res.set(field, value)
            has_changes = True

    if has_changes or res.is_new():
        res.flags.ignore_mandatory = True
        res.save(ignore_permissions=True)
    
    return res.name

@frappe.whitelist()
def bulk_sync_from_applicants(admission_cycle, campus, program_level=None):
    """
    Creates Admission Result records for all applicants in a specific cycle and campus.
    """
    eval_filters = {
        "admission_cycle": admission_cycle,
        "campus": campus,
        "evaluation_status": "Eligible"
    }

    evaluations = frappe.get_all("Eligibility Evaluation", filters=eval_filters, fields=["applicant_name"])
    
    count = 0
    for eval_doc in evaluations:
        app_name = eval_doc.applicant_name
        
        # Security/Consistency: If program_level filter is provided, check it on the Applicant
        if program_level:
            app_program_level = frappe.db.get_value("Applicant", app_name, "program_level")
            if app_program_level != program_level:
                continue

        # Check if result already exists
        if not frappe.db.exists("Admission Result", {"applicant_id": app_name}):
            sync_applicant_to_admission_result(app_name)
            count += 1
        
    frappe.db.commit()
    return count
