import frappe


@frappe.whitelist()
def update_profile(**kwargs):
    """
    Update personal details on the Applicant record for the logged-in user.
    Called from the Profile tab edit modal via apiFetch.
    """
    if frappe.session.user == "Guest":
        frappe.throw("Not allowed", frappe.AuthenticationError)

    _user = frappe.session.user

    # Find the applicant record owned by this user
    apps = frappe.get_all("Applicant",
        filters=[["owner", "=", _user]],
        fields=["name"], limit=1, order_by="creation desc")
    if not apps:
        apps = frappe.get_all("Applicant",
            filters=[["email", "=", _user]],
            fields=["name"], limit=1, order_by="creation desc")

    if not apps:
        return {"success": False, "error": "No application found for your account."}

    app_name = apps[0].name

    # Allowed fields to update
    allowed = {
        "candidate_name", "date_of_birth", "gender", "nationality",
        "religion", "mobile_number", "alternate_contact", "id_proof",
        "correspondence_address", "city", "state", "pincode", "candidate_photo"
    }

    update_dict = {}
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            update_dict[k] = v if v != "" else None

    if not update_dict:
        return {"success": False, "error": "Nothing to update."}

    try:
        doc = frappe.get_doc("Applicant", app_name)
        for k, v in update_dict.items():
            setattr(doc, k, v)
        doc.save(ignore_permissions=False)
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Profile update failed")
        return {"success": False, "error": str(e)}
