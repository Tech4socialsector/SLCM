import frappe
from frappe import _

@frappe.whitelist()
def get_offer_details(offer_name=None):
    """
    Fetches details of a specific offer letter or the latest active one.
    Supports Admin view.
    """
    user = frappe.session.user
    if user == "Guest":
        return {"error": "Authentication required"}

    roles = frappe.get_roles(user)
    is_admin = "Administrator" in roles or "System Manager" in roles

    # Find applicant linked to this user for default filtering
    applicant = frappe.db.get_value("Applicant", {"email": user}, "name")
    if not applicant and frappe.db.exists("Applicant", user):
        applicant = user

    if offer_name:
        # Verify the offer exists. If not admin, verify it belongs to this applicant.
        check_filters = {"name": offer_name}
        if not is_admin:
            if not applicant:
                return {"error": "Applicant record not found for the current user"}
            check_filters["applicant"] = applicant

        if not frappe.db.exists("Offer Letter", check_filters):
            return {"error": _("Offer Letter {0} not found or access denied.").format(offer_name)}
        offer_id = offer_name
    else:
        # User is looking for their own latest offer
        if not applicant:
            return {"error": "Applicant record not found for the current user"}
            
        offers = frappe.get_all("Offer Letter", filters={
            "applicant": applicant,
            "offer_status": ["in", ["Issued", "Accepted"]]
        }, fields=["name"], order_by="creation desc", limit=1)
        
        if not offers:
            return {"error": "No active admission offer found at this time."}
        offer_id = offers[0].name

    offer_doc = frappe.get_doc("Offer Letter", offer_id)
    
    # Always use the applicant from the actual offer doc for metadata
    target_applicant = offer_doc.applicant
    
    # Get Snapshot or Live Fee Details
    fee_data = []
    snapshot = frappe.get_all("Offer Fee Snapshot", filters={"offer_id": offer_doc.name}, order_by="creation desc", limit=1)
    if snapshot:
        snapshot_doc = frappe.get_doc("Offer Fee Snapshot", snapshot[0].name)
        for comp in snapshot_doc.fee_component:
            fee_data.append({
                "component": comp.component_name or comp.fee_component,
                "amount": comp.total_amount or comp.amount
            })
    elif offer_doc.fee_structure:
        fs_doc = frappe.get_doc("Fee Structure", offer_doc.fee_structure)
        for comp in fs_doc.components:
            fee_data.append({
                "component": comp.component_name or comp.fee_component,
                "amount": comp.total_amount or comp.amount
            })
    
    return {
        "offer": offer_doc.as_dict(),
        "applicant": frappe.get_doc("Applicant", target_applicant).as_dict(),
        "fee_breakdown": fee_data,
        "rendered_content": offer_doc.rendered_content,
        "is_admin": is_admin,
        "currency": frappe.defaults.get_global_default("currency") or "INR"
    }
