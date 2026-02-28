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
    if scheme.status != "Active" or not scheme.is_active:
        frappe.throw(frappe._("Scholarship scheme {0} is not active").format(scheme_name))

    # 2. Stage check
    if scheme.stage_availability == "Post-Selection" and applicant_status != "Selected":
        frappe.throw(frappe._("Scholarship available only after selection"))

    if scheme.stage_availability == "Post-Offer" and applicant_status != "Offered":
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
