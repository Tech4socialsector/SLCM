import frappe

@frappe.whitelist()
def check_existing_application(admission_cycle=None):
    """
    Returns existing application name if user already applied in this cycle.
    Called from /admission page before showing Apply Now.
    """
    if frappe.session.user == "Guest":
        return {"exists": False, "name": ""}

    filters = {"owner": frappe.session.user}
    if admission_cycle:
        filters["admission_cycle"] = admission_cycle

    existing = frappe.get_all(
        "Applicant",
        filters=filters,
        fields=["name", "admission_cycle", "application_status"],
        order_by="creation desc",
        limit=1
    )
    if existing:
        return {
            "exists":  True,
            "name":    existing[0].name,
            "status":  existing[0].application_status,
            "cycle":   existing[0].admission_cycle,
        }
    return {"exists": False, "name": ""}

@frappe.whitelist()
def mark_notifications_read(names=None):
    """Marks unread notifications as read. If names provided, only those."""
    user = frappe.session.user
    if user == "Guest":
        return

    try:
        if not names: return
        if isinstance(names, str):
            import json as _json
            try:
                names = _json.loads(names)
            except Exception:
                names = [names]

        # Get applicant records for this user to ensure they own these notifications
        applicant_names = frappe.get_all(
            "Applicant",
            filters={"email": user},
            pluck="name"
        )
        if not applicant_names:
            return
            
        filters = {
            "applicant": ["in", applicant_names],
            "name": ["in", names]
        }

        frappe.db.set_value(
            "Applicant Notification",
            filters,
            "is_read", 1
        )
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.log_error(f"mark_notifications_read failed: {e}", "Portal")
        return {"success": False}

@frappe.whitelist()
def get_portal_notifications():
    try:
        user = frappe.session.user
        if user == "Guest":
            return {"notifications": [], "announcements": []}

        # Get applicant records for this user
        applicant_names = frappe.get_all(
            "Applicant",
            filters={"email": user},
            pluck="name"
        )

        notifications = []
        if applicant_names:
            notifications = frappe.get_all(
                "Applicant Notification",
                filters={"applicant": ["in", applicant_names]},
                fields=["name", "notification_type as title", "message", "is_read",
                        "created_on as creation", "owner", "announcement"],
                order_by="created_on desc",
                limit=15
            )
            for n in notifications:
                try:
                    n["owner_fullname"] = frappe.db.get_value("User", n.owner, "full_name") or n.owner
                    if n.announcement:
                        n["image"] = frappe.db.get_value("Portal Announcement", n.announcement, "featured_image")
                except:
                    n["owner_fullname"] = ""

        announcements = frappe.get_all(
            "Portal Announcement",
            filters={"is_active": 1},
            fields=["name", "title", "publish_date", "announcement_type",
                    "summary as content", "featured_image as image", "owner"],
            order_by="publish_date desc",
            limit=10
        )
        for a in announcements:
            try:
                a["owner_fullname"] = frappe.db.get_value("User", a.owner, "full_name") or a.owner
            except:
                a["owner_fullname"] = ""

        return {"notifications": notifications, "announcements": announcements}
    except Exception as e:
        frappe.log_error(f"get_portal_notifications failed: {e}", "Portal")
        return {"notifications": [], "announcements": []}

@frappe.whitelist(allow_guest=True)
def get_public_announcements():
    """Returns announcements visible without login"""
    try:
        ann = frappe.get_all("Portal Announcement",
            filters={"is_active": 1},
            fields=["name", "title", "publish_date",
                    "announcement_type", "summary as content",
                    "featured_image", "owner"],
            order_by="publish_date desc",
            limit=10)
        
        for a in ann:
            try:
                a["owner_fullname"] = frappe.db.get_value("User", a.owner, "full_name") or a.owner
            except:
                a["owner_fullname"] = ""
                
        return ann or []
    except Exception as e:
        frappe.log_error(f"get_public_announcements failed: {e}", "Portal")
        return []

@frappe.whitelist()
def get_user_type():
    """Returns user_type for the currently logged-in user"""
    try:
        user_type = frappe.db.get_value("User", frappe.session.user, "user_type")
        return {"user_type": user_type or "Website User"}
    except Exception as e:
        frappe.log_error(f"get_user_type failed: {e}", "Portal")
        return {"user_type": "Website User"}

@frappe.whitelist()
def submit_application(application_data):
    """
    Called from /application-form JS to submit/save application.
    """
    if isinstance(application_data, str):
        import json as _json
        application_data = _json.loads(application_data)
        
    user = frappe.session.user
    if user == "Guest":
        # Usually we'd want them to log in, but let's allow it if config says so
        config = frappe.get_single("Applicant Portal Config")
        if config.login_required_for_application:
            frappe.throw("Login required to submit application")
            
    # Check if existing applicant for this email
    email = application_data.get("email") or user
    existing = frappe.get_all("Applicant", filters={"email": email}, limit=1)
    
    if existing:
        doc = frappe.get_doc("Applicant", existing[0].name)
    else:
        doc = frappe.new_doc("Applicant")
        doc.email = email
        
    # List of known phone fields for Applicant
    phone_fields = ["mobile_number", "alternate_contact", "father_mobile", "mother_mobile", "guardian_mobile"]

    # Update with fields
    for fieldname, value in application_data.items():
        if doc.get(fieldname) is not None:
            if fieldname in phone_fields and value:
                # Basic formatting for Indian numbers if digits only
                raw_value = str(value).replace(" ", "").replace("-", "")
                if raw_value.isdigit() and len(raw_value) == 10:
                    value = "+91" + raw_value
                elif raw_value.isdigit() and len(raw_value) > 10 and not raw_value.startswith("+"):
                    value = "+" + raw_value
            doc.set(fieldname, value)
            
    try:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
    except frappe.exceptions.InvalidPhoneNumberError as e:
        frappe.log_error(f"Phone validation failed: {str(e)}", "Admission Form")
        frappe.throw(f"Validation failed: {str(e)}")
    except Exception as e:
        frappe.log_error(f"Submission error: {str(e)}", "Admission Form")
        frappe.throw(str(e))
    
    return doc.name
