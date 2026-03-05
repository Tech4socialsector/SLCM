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

        # Use get_all with ignore_permissions to check existence for website users
        exists = frappe.get_all("Offer Letter", filters=check_filters, limit=1, ignore_permissions=True)
        if not exists:
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
            "offer_status": ["in", ["Issued", "Accepted", "Payment Completed"]]

        }, fields=["name"], order_by="creation desc", limit=1, ignore_permissions=True)
        
        if not offers:
            return {"error": _("No active admission offer found for your account at this time.")}
        offer_id = offers[0].name


    # If get_doc fails due to permission, we'll fetch fields manually with ignore_permissions
    try:
        offer_doc = frappe.get_doc("Offer Letter", offer_id)
        offer_dict = offer_doc.as_dict()
        rendered_content = offer_doc.rendered_content
        target_applicant = offer_doc.applicant
        fee_structure = offer_doc.fee_structure
    except frappe.PermissionError:
        # Fallback for website users with restricted desk access
        offer_fields = frappe.get_all("Offer Letter", filters={"name": offer_id}, fields=["*"], limit=1, ignore_permissions=True)
        if not offer_fields:
            return {"error": _("Access Denied")}
        offer_dict = offer_fields[0]
        rendered_content = offer_dict.get("rendered_content")
        target_applicant = offer_dict.get("applicant")
        fee_structure = offer_dict.get("fee_structure")

    # Get Snapshot or Live Fee Details
    fee_data = []
    snapshot = frappe.get_all("Offer Fee Snapshot", filters={"offer_id": offer_id}, order_by="creation desc", limit=1, ignore_permissions=True)
    if snapshot:
        snapshot_items = frappe.get_all("Fee Component Child", 
            filters={"parent": snapshot[0].name, "parenttype": "Offer Fee Snapshot"}, 
            fields=["component_name", "fee_component", "total_amount", "amount"],
            ignore_permissions=True
        )
        for comp in snapshot_items:
            fee_data.append({
                "component": comp.component_name or comp.fee_component,
                "amount": comp.total_amount or comp.amount
            })
    elif fee_structure:
        fs_components = frappe.get_all("Fee Component Child", 
            filters={"parent": fee_structure, "parenttype": "Fee Structure"}, 
            fields=["component_name", "fee_component", "total_amount", "amount"],
            ignore_permissions=True
        )
        for comp in fs_components:
            fee_data.append({
                "component": comp.component_name or comp.fee_component,
                "amount": comp.total_amount or comp.amount
            })

    
    # Check if Fee is paid
    fee_paid = frappe.db.get_value("Applicant Fee Assignment", 
        {"offer_letter": offer_id, "status": ["in", ["Paid", "Fee Paid"]]}, "name")

    # Get Online Payment Enabled flag
    online_payment_enabled = frappe.db.get_value("Fee Structure", fee_structure, "online_payment") if fee_structure else False

    # Get Applicant data safely
    applicant_data = frappe.get_all("Applicant", filters={"name": target_applicant}, fields=["*"], limit=1, ignore_permissions=True)
    applicant_dict = applicant_data[0] if applicant_data else {}

    return {
        "offer": offer_dict,
        "applicant": applicant_dict,
        "fee_breakdown": fee_data,
        "rendered_content": rendered_content,
        "is_admin": is_admin,
        "is_fee_paid": True if fee_paid else False,
        "online_payment_enabled": online_payment_enabled,
        "currency": frappe.defaults.get_global_default("currency") or "INR"
    }


