import frappe
from frappe.utils import now_datetime

def check_scholarship_availability(scheme_name, applicant_status):
    """
    Checks if a scholarship scheme is available for an applicant based on:
    1. Active status
    2. Admission stage
    3. Date window
    4. Beneficiary limits
    5. Budget limits
    """
    scheme = frappe.get_doc("Scholarship Scheme", scheme_name)

    # 1. Scheme must be active
    if scheme.status != "Active":
        frappe.throw(frappe._("Scholarship scheme {0} is not active").format(scheme_name))

    # 2. Stage check
    valid_offer_statuses = ["Offer Issued", "Offer Accepted", "Fee Paid"]
    
    if scheme.stage_availability == "Post-Selection" and applicant_status not in ["Selected"] + valid_offer_statuses:
        frappe.throw(frappe._("Scholarship available only after selection"))

    if scheme.stage_availability == "Post-Offer" and applicant_status not in valid_offer_statuses:
        frappe.throw(frappe._("Scholarship available only after offer issuance"))

    # 3. Date window check
    now = now_datetime()

    if scheme.application_start and now < scheme.application_start:
        frappe.throw(frappe._("Scholarship application not started"))

    if scheme.application_end and now > scheme.application_end:
        frappe.throw(frappe._("Scholarship application closed"))

    # 4. Beneficiary limit
    if scheme.max_beneficiaries:
        if scheme.current_beneficiaries >= scheme.max_beneficiaries:
            frappe.throw(frappe._("Scholarship limit reached"))

    # 5. Budget control
    if scheme.total_budget:
        if scheme.utilized_budget >= scheme.total_budget:
            frappe.throw(frappe._("Scholarship budget exhausted"))

def update_scheme_usage(scheme_name, approved_amount):
    """
    Updates the beneficiary count and utilized budget for a scholarship scheme.
    Auto-archives the scheme if limits are reached.
    """
    scheme = frappe.get_doc("Scholarship Scheme", scheme_name)

    scheme.current_beneficiaries += 1
    scheme.utilized_budget += approved_amount

    # Auto close if limits reached
    if scheme.max_beneficiaries and scheme.current_beneficiaries >= scheme.max_beneficiaries:
        scheme.status = "Archived"

    if scheme.total_budget and scheme.utilized_budget >= scheme.total_budget:
        scheme.status = "Archived"

    scheme.save(ignore_permissions=True)

def get_applied_scholarships_for_dashboard(applicant_id):
    """
    Fetches all scholarship applications for a specific applicant to display on the portal.
    """
    return frappe.get_all(
        "Scholarship Application",
        filters={"applicant_id": applicant_id},
        fields=["name", "scholarship_scheme", "status", "calculated_benefit", "creation"],
        order_by="creation desc"
    )

def get_available_scholarships_for_dashboard(applicant_id, cycle, campus, program, applicant_statuses):
    """
    Determines which scholarship schemes are currently available for this applicant 
    to apply for. 
    applicant_statuses should be a list of statuses (e.g. from their admission results/preferences).
    """
    # 1. Get all schemes mapped to this cycle + campus
    mappings = frappe.get_all(
        "Scholarship Scheme Mapping",
        filters={
            "admission_cycle": cycle,
            "campus": campus,
        },
        fields=["scholarship_scheme", "program", "category"]
    )
    
    if not mappings:
        return []

    # Get applicant categories for filtering
    from slcm.admission.doctype.seat_allocation.seat_allocation import get_applicant_categories
    applicant_categories = get_applicant_categories(applicant_id)

    applicable_schemes = []
    for m in mappings:
        # Check program match
        program_match = not m.program or m.program == program
        
        # Check category match (if mapping has category, student must have it in their multi-category list)
        category_match = not m.category or m.category in applicant_categories
        
        if program_match and category_match:
            applicable_schemes.append(m.scholarship_scheme)

    if not applicable_schemes:
        return []

    # 2. Filter schemes that are Active and within application dates
    now = now_datetime()
    schemes = frappe.get_all(
        "Scholarship Scheme",
        filters={
            "name": ["in", applicable_schemes],
            "status": "Active"
        },
        fields=["name", "scheme_name", "coverage_type", "coverage_value", "apply_on", "stage_availability", "application_start", "application_end", "max_beneficiaries", "current_beneficiaries", "total_budget", "utilized_budget", "exclusive_scheme"]
    )
    
    available = []
    
    # Get schemes already applied for
    applied_docs = frappe.get_all("Scholarship Application", 
        filters={"applicant_id": applicant_id, "status": ["not in", ["Rejected", "Revoked"]]}, 
        fields=["scholarship_scheme", "status"]
    )
    applied_scheme_names = [d.scholarship_scheme for d in applied_docs]
    approved_scheme_names = [d.scholarship_scheme for d in applied_docs if d.status == "Approved"]

    # Check if applicant already has an APPROVED Exclusive scholarship
    has_exclusive = frappe.db.exists("Scholarship Application", {
        "applicant_id": applicant_id,
        "status": "Approved",
        "scholarship_scheme": ["in", frappe.get_all("Scholarship Scheme", filters={"exclusive_scheme": 1}, pluck="name")]
    })

    # Get Max Schemes limit from Cycle
    cycle_limit = frappe.db.get_value("Admission Cycle", cycle, "max_schemes_per_applicant") or 0

    for scheme in schemes:
        # Skip if already applied (even if not yet approved)
        if scheme.name in applied_scheme_names:
            continue
            
        # 1. Exclusive Check: If they have an exclusive one, they see nothing else.
        if has_exclusive:
            continue
            
        # 2. If THIS scheme is exclusive, they can only see it if they have ZERO approved schemes.
        if scheme.exclusive_scheme and len(approved_scheme_names) > 0:
            continue
            
        # 3. Max Schemes Check: If they already reached the limit for this cycle
        if cycle_limit > 0:
            if len(approved_scheme_names) >= cycle_limit:
                continue

        # Check dates
        if scheme.application_start and now < scheme.application_start:
            continue
        if scheme.application_end and now > scheme.application_end:
            continue
            
        # Check stage availability
        is_eligible_stage = True
        valid_post_offer = ["Offer Issued", "Offer Accepted", "Fee Paid"]
        
        if scheme.stage_availability == "Post-Selection":
            if "Selected" not in applicant_statuses and not any(s in applicant_statuses for s in valid_post_offer):
                is_eligible_stage = False
        elif scheme.stage_availability == "Post-Offer":
            if not any(s in applicant_statuses for s in valid_post_offer):
                is_eligible_stage = False
                
        if not is_eligible_stage:
            continue

        # Check Limits
        if scheme.max_beneficiaries and scheme.current_beneficiaries >= scheme.max_beneficiaries:
            continue
        if scheme.total_budget and scheme.utilized_budget >= scheme.total_budget:
            continue
            
        available.append(scheme)
        
    return available
