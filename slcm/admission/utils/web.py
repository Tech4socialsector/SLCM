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
def get_stage_tracker_data(applicant_name):
    """
    Returns stage pipeline for /my-applications stage tracker widget.
    Reads stages from Admission Cycle child table filtered by intake_type.
    """
    # Permission: owner or admin
    applicant = frappe.get_doc("Applicant", applicant_name)
    allowed_roles = {"Admission Admin", "System Manager", "Applicant"}
    is_owner = frappe.session.user == applicant.owner
    has_role = bool(allowed_roles & set(frappe.get_roles()))
    if not is_owner and not has_role:
        frappe.throw("Not permitted", frappe.PermissionError)

    if not applicant.admission_cycle:
        return {"stages": [], "app_status": applicant.application_status or ""}

    # Get intake_type from Admission Cycle (not Program)
    intake_type = frappe.db.get_value(
        "Admission Cycle", applicant.admission_cycle, "intake_type"
    ) or "All"

    # Load stages from cycle child table
    try:
        from slcm.admission.utils.stage_control import get_cycle_stages
        stages = get_cycle_stages(applicant.admission_cycle, intake_type)
    except Exception as e:
        frappe.log_error(f"get_stage_tracker_data stage load error: {e}")
        stages = []

    if not stages:
        return {"stages": [], "app_status": applicant.application_status or ""}

    from frappe.utils import today as get_today
    today = get_today()
    current_stage_name = applicant.current_stage or ""

    # Determine status of each stage
    result_stages = []
    found_active = False

    def get_seq(s):
        return getattr(s, "sequence", None) or getattr(s, "sequence_no", None) or 0

    for s in stages:
        sd = str(getattr(s, "start_date", None) or getattr(s, "stage_start_date", None) or "")
        ed = str(getattr(s, "end_date", None) or getattr(s, "stage_end_date", None) or "")

        # Determine status
        if sd and ed:
            if today > ed:
                status = "completed"
            elif sd <= today <= ed:
                status = "active"
                found_active = True
            else:
                status = "pending"
        elif current_stage_name:
            if s.stage_name == current_stage_name:
                status = "active"
                found_active = True
            elif not found_active:
                status = "completed"
            else:
                status = "pending"
        else:
            status = "pending"

        # Check for applicant action on this stage
        show_action = (
            status == "active" and
            bool(getattr(s, "requires_applicant_action", 0))
        )
        action_url   = getattr(s, "action_url", "") or ""
        action_label = getattr(s, "action_label", "") or ""

        # Override action_url for known stage types
        stage_type = getattr(s, "stage_type", "") or ""
        if status == "active" and not action_url:
            if stage_type == "Interview":
                action_url   = "/eligibility/interview_management"
                action_label = "View Interview"
                show_action  = True
            elif stage_type == "Exam":
                action_url   = "/eligibility/entrance_test_seat_allocation"
                action_label = "View Exam Details"
                show_action  = True
            elif stage_type == "Offer Letter":
                action_url   = "/offer_letter/offer-letter-list"
                action_label = "View Offer"
                show_action  = True

        result_stages.append({
            "stage_name":    s.stage_name,
            "stage_type":    stage_type,
            "sequence":      get_seq(s),
            "status":        status,
            "reached_on":    sd if status == "completed" else "",
            "show_action":   show_action,
            "action_url":    action_url,
            "action_label":  action_label,
        })

    return {
        "stages":     result_stages,
        "app_status": applicant.application_status or "",
        "track_type": "normal",
    }



@frappe.whitelist()
def get_edit_permission(applicant_name):
    """
    Returns whether the current applicant can edit their application.
    Two-layer check:
      Layer 1: Portal Config master switch (allow_edit_after_submit)
      Layer 2: Current stage is_editable flag
    """
    import frappe

    # Load applicant
    applicant = frappe.get_doc("Applicant", applicant_name)

    # Only owner can check own permissions
    allowed_roles = {"Admission Admin", "System Manager", "Applicant"}
    is_owner = frappe.session.user == applicant.owner
    has_role = bool(allowed_roles & set(frappe.get_roles()))
    if not is_owner and not has_role:
        return {"editable": False, "reason": "Not permitted"}

    # Draft is always editable
    if applicant.docstatus == 0:
        return {"editable": True, "reason": "draft", "editable_sections": []}

    # Layer 1: Portal Config master switch
    try:
        portal_config = frappe.get_single("Admission Portal Config")
        if not portal_config.allow_edit_after_submit:
            return {
                "editable": False,
                "reason": "Editing is currently disabled by the administrator."
            }
    except Exception:
        # If Portal Config not found, deny by default
        return {"editable": False, "reason": "Portal config not found"}

    # Layer 2: Current stage is_editable flag
    if not applicant.admission_cycle or not applicant.current_stage:
        return {"editable": False, "reason": "No active stage found"}

    cycle_doc = frappe.get_doc("Admission Cycle", applicant.admission_cycle)
    current_stage_row = next(
        (s for s in cycle_doc.stages
         if s.stage_name == applicant.current_stage),
        None
    )

    if not current_stage_row:
        return {"editable": False, "reason": "Current stage not configured"}

    if not current_stage_row.is_editable:
        return {
            "editable": False,
            "reason": f"Editing is not allowed during the {applicant.current_stage} stage."
        }

    return {
        "editable":          True,
        "reason":            "stage_allows",
        "editable_sections": [],   # empty = all sections editable
    }
