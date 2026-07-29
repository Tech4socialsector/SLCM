import frappe
from frappe import _
from frappe.utils import flt

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
        # Verify the offer exists. If not admin, verify it belongs to this user's email.
        check_filters = {"name": offer_name}
        if not is_admin:
            check_filters["email"] = user

        # Use get_all with ignore_permissions to check existence for website users
        exists = frappe.get_all("Offer Letter", filters=check_filters, limit=1, ignore_permissions=True)
        if not exists:
            return {"error": _("Offer Letter {0} not found or you don't have permission to view it.").format(offer_name)}
        offer_id = offer_name
    else:
        # User is looking for their own latest offer
        latest_filters = {
            "status": ["in", ["Issued", "Accepted", "Payment Completed"]]
        }
        if not is_admin:
            latest_filters["email"] = user
            
        offers = frappe.get_all("Offer Letter", 
            filters=latest_filters, 
            fields=["name"], 
            order_by="creation desc", 
            limit=1, 
            ignore_permissions=True
        )
        
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

    # Get Live Fee Details
    fee_data = []

    # First, try to fetch components from Applicant Fee Assignment (AFA)
    afa = frappe.db.get_value("Applicant Fee Assignment",
        {"offer_letter": offer_id, "fee_type": ["in", ["Admission Fee", "Confirmation Fee"]], "docstatus": ["!=", 2]},
        ["name", "final_payable_amount", "scholarship_amount", "scholarship_applied", "total_amount", "fee_type", "confirmation_fee"],
        as_dict=True)

    if afa:
        if afa.final_payable_amount is not None:
            offer_dict["payable_amount"] = afa.final_payable_amount
            
        if afa.fee_type == "Confirmation Fee":
            fee_data.append({
                "component": "Confirmation Fee",
                "amount": afa.confirmation_fee or afa.total_amount
            })
        else:
            afa_components = frappe.get_all("Applicant Fee Component Child",
                filters={"parent": afa.name, "parenttype": "Applicant Fee Assignment"},
                fields=["component_name", "fee_component", "total_amount", "amount"],
                ignore_permissions=True
            )
            for comp in afa_components:
                fee_data.append({
                    "component": comp.component_name or comp.fee_component,
                    "amount": comp.total_amount or comp.amount
                })

    # If AFA doesn't have components or doesn't exist, fallback to Fee Structure
    if not fee_data and fee_structure:
        # Determine nationality for parentfield
        applicant_nationality = "Indian"
        if target_applicant:
            applicant_nationality = frappe.db.get_value("Applicant", target_applicant, "nationality") or "Indian"

        parentfield = "fee_components_for_indian" if applicant_nationality.strip().lower() == "indian" else "fee_components_for_foreign"

        fs_doc = frappe.get_doc("Fee Structure", fee_structure)
        if fs_doc.is_confirmation_fee_applicable:
            fee_data.append({
                "component": "Confirmation Fee",
                "amount": fs_doc.confirmation_fee_amount
            })
        else:
            fs_components = frappe.get_all("Fee Component Child",
                filters={"parent": fee_structure, "parenttype": "Fee Structure", "parentfield": parentfield},
                fields=["component_name", "fee_component", "total_amount", "amount"],
                ignore_permissions=True
            )
            for comp in fs_components:
                fee_data.append({
                    "component": comp.component_name or comp.fee_component,
                    "amount": comp.total_amount or comp.amount
                })

    # Check if Fee is paid: AFA status Paid/Converted, or Payment Request for this offer is Paid
    fee_paid = frappe.db.get_value("Applicant Fee Assignment",
        {"offer_letter": offer_id, "status": ["in", ["Paid", "Converted"]]}, "name")
    if not fee_paid:
        fee_paid = frappe.db.get_value("Payment Request",
            {"reference_doctype": "Offer Letter", "reference_name": offer_id, "status": "Paid"}, "name")

    # Scholarship Amount: prefer live total from Scholarship Application (most accurate)
    applicant_id = target_applicant
    admission_cycle = offer_dict.get("admission_cycle") or frappe.db.get_value("Applicant", applicant_id, "admission_cycle")
    live_scholarship = frappe.db.sql("""
        SELECT SUM(calculated_benefit)
        FROM `tabScholarship Application`
        WHERE applicant_id = %s AND admission_cycle = %s AND status = 'Approved'
    """, (applicant_id, admission_cycle))[0][0] or 0
    scholarship_amount = flt(live_scholarship)
    offer_dict["scholarship_amount"] = scholarship_amount

    # Get Online Payment Enabled flag
    online_payment_enabled = frappe.db.get_value("Fee Structure", fee_structure, "online_payment") if fee_structure else False

    # --- Scholarship: Get latest application status and benefit ---
    scholarship_data = None
    latest_sa = frappe.get_all("Scholarship Application",
        filters={"applicant_id": applicant_id, "admission_cycle": admission_cycle, "docstatus": ["!=", 2]},
        fields=["name", "status", "scholarship_scheme", "calculated_benefit", "original_fee_amount", "final_fee_amount", "income_certificate", "supporting_documents"],
        order_by="creation desc",
        limit=1
    )
    if latest_sa:
        scholarship_data = latest_sa[0]
        # Status normalization for frontend
        if scholarship_data.status == "Submitted":
            scholarship_data.status = "Submitted" # Under Review

    # --- Scholarship: Override payable_amount with scholarship-adjusted amount ---
    applied_scholarship = 0
    if afa and afa.scholarship_applied and flt(afa.scholarship_amount) > 0:
        # Show the scholarship-reduced amount as the payable amount
        offer_dict["payable_amount"] = flt(afa.final_payable_amount)
        applied_scholarship = flt(afa.scholarship_amount)
    elif scholarship_data and scholarship_data.status == "Approved":
        # Fallback: if AFA not created yet, show potential reduced amount in portal
        benefit = flt(scholarship_data.calculated_benefit)
        offer_dict["payable_amount"] = max(0, flt(offer_dict["payable_amount"]) - benefit)
        applied_scholarship = benefit

    # Append scholarship deduction row to fee breakdown if applicable
    if applied_scholarship > 0:
        fee_data.append({
            "component": "Scholarship Benefit",
            "amount": -applied_scholarship,
            "is_discount": True
        })

    # Get Applicant data safely
    applicant_data = frappe.get_all("Applicant", filters={"name": target_applicant}, fields=["*"], limit=1, ignore_permissions=True)
    applicant_dict = applicant_data[0] if applicant_data else {}
    if applicant_dict and not applicant_dict.get("candidate_photo"):
        applicant_dict["candidate_photo"] = frappe.db.get_value("User", frappe.session.user, "user_image")

    # Fetch cancellation info
    cancellation = frappe.get_all("Admission Cancellation", 
        filters={"offer": offer_id}, 
        fields=["name", "status"], 
        limit=1
    )
    cancellation_info = {
        "has_cancellation": True if cancellation else False,
        "cancellation_name": cancellation[0].name if cancellation else "",
        "cancellation_status": cancellation[0].status if cancellation else ""
    }

    # Calculate available scholarships
    from slcm.admission.utils.scholarship_availability import get_available_scholarships_for_dashboard
    available_scholarships_count = 0
    enable_scholarship = frappe.db.get_value("Admission Cycle", admission_cycle, "enable_scholarship")
    if enable_scholarship:
        try:
            available_scholarships = get_available_scholarships_for_dashboard(
                applicant_id=target_applicant,
                cycle=admission_cycle,
                campus=applicant_dict.get("campus"),
                program=applicant_dict.get("program"),
                applicant_statuses=[applicant_dict.get("status")]
            )
            available_scholarships_count = len(available_scholarships)
        except Exception:
            pass

    return {
        "offer": offer_dict,
        "applicant": applicant_dict,
        "fee_breakdown": fee_data,
        "rendered_content": rendered_content,
        "is_admin": is_admin,
        "is_fee_paid": True if fee_paid else False,
        "online_payment_enabled": online_payment_enabled,
        "currency": frappe.defaults.get_global_default("currency") or "INR",
        "cancellation": cancellation_info,
        "available_scholarships_count": available_scholarships_count,
        "scholarship_application": scholarship_data
    }


