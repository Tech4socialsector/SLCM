import frappe
from frappe import _
from frappe.utils import flt

@frappe.whitelist(allow_guest=True)
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

    try:
        offer_doc = frappe.get_doc("Offer Letter", offer_id)
        offer_dict = offer_doc.as_dict()
        rendered_content = offer_doc.rendered_content
        target_applicant = offer_doc.applicant
        fee_structure = offer_doc.fee_structure
    except frappe.PermissionError:
        offer_fields = frappe.get_all("Offer Letter", filters={"name": offer_id}, fields=["*"], limit=1, ignore_permissions=True)
        if not offer_fields:
            return {"error": _("Access Denied")}
        offer_dict = offer_fields[0]
        rendered_content = offer_dict.get("rendered_content")
        target_applicant = offer_dict.get("applicant")
        fee_structure = offer_dict.get("fee_structure")

    fee_data = []

    # First, try to fetch pending components from Applicant Fee Assignment (AFA)
    afa = frappe.db.get_value("Applicant Fee Assignment",
        {"offer_letter": offer_id, "fee_type": ["in", ["Admission Fee", "Confirmation Fee"]], "status": "Assigned", "docstatus": ["!=", 2]},
        ["name", "final_payable_amount", "scholarship_amount", "scholarship_applied", "total_amount", "fee_type", "confirmation_fee"],
        order_by="creation desc",
        as_dict=True)

    if not afa:
        afa = frappe.db.get_value("Applicant Fee Assignment",
            {"offer_letter": offer_id, "fee_type": ["in", ["Admission Fee", "Confirmation Fee"]], "docstatus": ["!=", 2]},
            ["name", "final_payable_amount", "scholarship_amount", "scholarship_applied", "total_amount", "fee_type", "confirmation_fee"],
            order_by="creation desc",
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

    if not fee_data and fee_structure:
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

    fee_paid = (offer_dict.get("status") == "Payment Completed")
    if not fee_paid:
        is_admission_paid = frappe.db.get_value("Applicant Fee Assignment",
            {"offer_letter": offer_id, "fee_type": "Admission Fee", "status": ["in", ["Paid", "Converted"]]}, "name")
        if is_admission_paid:
            fee_paid = True

    applicant_id = target_applicant
    admission_cycle = offer_dict.get("admission_cycle") or frappe.db.get_value("Applicant", applicant_id, "admission_cycle")
    live_scholarship_query = frappe.db.sql("""
        SELECT SUM(calculated_benefit)
        FROM `tabScholarship Application`
        WHERE applicant_id = %s AND admission_cycle = %s AND status = 'Approved'
    """, (applicant_id, admission_cycle))
    live_scholarship = live_scholarship_query[0][0] if live_scholarship_query and live_scholarship_query[0] else 0
    scholarship_amount = flt(live_scholarship)
    offer_dict["scholarship_amount"] = scholarship_amount

    online_payment_enabled = frappe.db.get_value("Fee Structure", fee_structure, "online_payment") if fee_structure else False

    scholarship_data = None
    latest_sa = frappe.get_all("Scholarship Application",
        filters={"applicant_id": applicant_id, "admission_cycle": admission_cycle, "docstatus": ["!=", 2]},
        fields=["name", "status", "scholarship_scheme", "calculated_benefit", "original_fee_amount", "final_fee_amount", "income_certificate", "supporting_documents"],
        order_by="creation desc",
        limit=1
    )
    if latest_sa:
        scholarship_data = latest_sa[0]
        if scholarship_data.status == "Submitted":
            scholarship_data.status = "Submitted"

    applied_scholarship = 0
    if afa and afa.scholarship_applied and flt(afa.scholarship_amount) > 0:
        offer_dict["payable_amount"] = flt(afa.final_payable_amount)
        applied_scholarship = flt(afa.scholarship_amount)
    elif scholarship_data and scholarship_data.status == "Approved":
        benefit = flt(scholarship_data.calculated_benefit)
        offer_dict["payable_amount"] = max(0, flt(offer_dict["payable_amount"]) - benefit)
        applied_scholarship = benefit

    if applied_scholarship > 0:
        fee_data.append({
            "component": "Scholarship Benefit",
            "amount": -applied_scholarship,
            "is_discount": True
        })

    applicant_data = frappe.get_all("Applicant", filters={"name": target_applicant}, fields=["*"], limit=1, ignore_permissions=True)
    applicant_dict = applicant_data[0] if applicant_data else {}
    if applicant_dict and not applicant_dict.get("candidate_photo"):
        applicant_dict["candidate_photo"] = frappe.db.get_value("User", frappe.session.user, "user_image")

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
