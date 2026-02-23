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
                return {"error": _("We couldn't find an applicant record linked to your account.")}
            check_filters["applicant"] = applicant

        if not frappe.db.exists("Offer Letter", check_filters):
            return {"error": _("Offer Letter {0} not found or you don't have permission to view it.").format(offer_name)}
        offer_id = offer_name
    else:
        # User is looking for their own latest offer
        if not applicant:
            if is_admin:
                return {"error": _("Please select an offer to view from the list.")}
            return {"error": _("We couldn't find an applicant record linked to your account.")}
            
        offers = frappe.get_all("Offer Letter", filters={
            "applicant": applicant,
            "offer_status": ["in", ["Issued", "Accepted"]]
        }, fields=["name"], order_by="creation desc", limit=1)
        
        if not offers:
            return {"error": _("No active admission offer found for your account at this time.")}
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
    
    # Check if Fee is paid
    fee_paid = frappe.db.get_value("Applicant Fee Assignment", 
        {"offer_letter": offer_doc.name, "status": "Paid"}, "name")

    return {
        "offer": offer_doc.as_dict(),
        "applicant": frappe.get_doc("Applicant", target_applicant).as_dict(),
        "fee_breakdown": fee_data,
        "rendered_content": offer_doc.rendered_content,
        "is_admin": is_admin,
        "is_fee_paid": True if fee_paid else False,
        "currency": frappe.defaults.get_global_default("currency") or "INR"
    }
