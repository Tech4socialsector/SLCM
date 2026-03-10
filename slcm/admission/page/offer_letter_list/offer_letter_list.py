import frappe
from frappe import _

@frappe.whitelist()
def get_offer_list(limit_start=0, limit_page_length=10):
    """
    Fetches offer letters with pagination. 
    If admin, fetches all. If applicant, fetches only theirs.
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Authentication required"), frappe.PermissionError)

    roles = frappe.get_roles(user)
    is_admin = "Administrator" in roles or "System Manager" in roles
    
    filters = {}
    applicant_name = "System View"
    
    if not is_admin:
        # User is an applicant, filter by their record
        applicant = frappe.db.get_value("Applicant", {"email": user}, "name")
        if not applicant:
            if frappe.db.exists("Applicant", user):
                applicant = user
            else:
                frappe.throw(_("Applicant record not found for user {0}").format(user))
        
        filters["applicant"] = applicant
        applicant_name = frappe.db.get_value("Applicant", applicant, "candidate_name") or applicant
    
    # Fetch total count for pagination
    total_count = frappe.db.count("Offer Letter", filters=filters)

    # Fetch offers
    fields = [
        "name", "program", "issued_on", "offer_status", 
        "payment_deadline", "payable_amount", "campus", "applicant"
    ]
    
    # Ensure integer types for pagination
    limit_start = int(limit_start)
    limit_page_length = int(limit_page_length)

    offers = frappe.get_all(
        "Offer Letter", 
        filters=filters, 
        fields=fields, 
        order_by="creation desc",
        limit_start=limit_start,
        limit_page_length=limit_page_length,
        ignore_permissions=True
    )

    for offer in offers:
        scholarship = frappe.db.get_value("Offer Fee Snapshot", {"offer_id": offer.name}, "scholarship_amount")
        offer["scholarship_amount"] = scholarship or 0

    return {
        "offers": offers,
        "total_count": total_count,
        "applicant_name": applicant_name,
        "is_admin": is_admin,
        "currency": frappe.defaults.get_global_default("currency") or "INR"
    }
