import frappe

@frappe.whitelist(allow_guest=True)
def check_existing_application(program):
    """
    Called from the /admission page JS before redirecting to application form.
    Checks if the logged-in user already has an application for this program.
    """
    user = frappe.session.user
    if user == "Guest":
        return {"exists": False}

    existing = frappe.db.get_value(
        "Applicant",
        {"email": user, "program": program},
        ["name", "application_status", "applicant_id"],
        as_dict=True
    )
    if existing:
        return {
            "exists": True,
            "status": existing.application_status or "Draft",
            "name": existing.name,
            "applicant_id": existing.applicant_id or existing.name
        }
    return {"exists": False}

@frappe.whitelist()
def mark_notifications_read():
    """Marks all unread notifications as read for logged-in user."""
    user = frappe.session.user
    if user == "Guest":
        return

    try:
        # Get applicant records for this user
        applicant_names = frappe.get_all(
            "Applicant",
            filters={"email": user},
            pluck="name"
        )
        if not applicant_names:
            return

        frappe.db.set_value(
            "Applicant Notification",
            {"applicant": ["in", applicant_names], "is_read": 0},
            "is_read", 1
        )
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.log_error(f"mark_notifications_read failed: {e}", "Portal")
        return {"success": False}
