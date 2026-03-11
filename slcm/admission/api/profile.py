import frappe


@frappe.whitelist(allow_guest=True, methods=["POST", "GET"])
def update_profile(**kwargs):
    """
    Update personal details on the Applicant record for the logged-in user.
    """
    # Applicants are usually Website Users, not Guest. 
    # But we whitelist guest to avoid desk-access redirects, then check manually.
    user = frappe.session.user
    if not user or user == "Guest":
        return {"success": False, "error": "Authentication required."}

    # Find the applicant record related to this user
    # Priority 1: Email match (official contact)
    # Priority 2: Owner match (creator)
    apps = frappe.get_all("Applicant",
        filters={"email": user},
        fields=["name"], limit=1, order_by="creation desc")
    
    if not apps:
        apps = frappe.get_all("Applicant",
            filters={"owner": user},
            fields=["name"], limit=1, order_by="creation desc")

    if not apps:
        return {"success": False, "error": "No application found for your account."}

    app_name = apps[0].name

    # Allowed fields to update via this endpoint
    allowed = {
        "candidate_name", "date_of_birth", "gender", "nationality",
        "mobile_number", "alternate_contact", "id_proof",
        "correspondence_address", "city", "state", "pincode", "candidate_photo"
    }

    from slcm.utils.phone_utils import sanitize_phone_for_frappe

    update_dict = {}
    for k, v in kwargs.items():
        if k in allowed:
            val = v if (v is not None and str(v).strip() != "") else None
            if k in ["mobile_number", "alternate_contact"] and val:
                val = sanitize_phone_for_frappe(val)
            update_dict[k] = val

    if not update_dict:
        return {"success": False, "error": "No valid fields provided for update."}

    try:
        # Load doc name and verify ownership
        # apps[0].name was already verified to belong to 'user' above.
        
        # Perform the update using db.set_value to bypass unrelated LinkValidationErrors
        # (e.g. if 'current_stage' contains a stale/invalid link)
        frappe.db.set_value("Applicant", app_name, update_dict)
        
        # If candidate_name was updated, also update the User's full_name for navbar consistency
        if "candidate_name" in update_dict and update_dict["candidate_name"]:
            frappe.db.set_value("User", user, "full_name", update_dict["candidate_name"])
            
        frappe.db.commit()
        
        return {"success": True, "status": "ok"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Profile update failed")
        return {"success": False, "error": str(e)}
