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
    Returns structured stage tracker data for the applicant portal.
    Consumed by stage_tracker.js on both:
      - /my-applications page (compact view)
      - /applicant-form/{name} page (full view)
    """
    import frappe

    # 1. Load applicant
    applicant = frappe.get_doc("Applicant", applicant_name)

    # 2. Permission check — only owner or admin
    allowed_roles = {"Admission Admin", "System Manager", "Applicant"}
    is_owner = frappe.session.user == applicant.owner
    has_role = bool(allowed_roles & set(frappe.get_roles()))
    if not is_owner and not has_role:
        frappe.throw("Not permitted", frappe.PermissionError)

    # 3. Get ordered enabled stages from Admission Cycle
    if not applicant.admission_cycle:
        return {"stages": [], "current_stage": None, "track_type": "normal"}

    cycle_doc = frappe.get_doc("Admission Cycle", applicant.admission_cycle)
    enabled_stages = sorted(
        [s for s in cycle_doc.stages if s.is_enabled],
        key=lambda s: s.sequence_no or 0
    )

    # 4. Determine track type
    status = applicant.application_status or ""
    if status == "Waitlisted":
        track_type = "waitlisted"
    elif status in ("Offer Issued", "Offer Accepted", "Fee Paid"):
        track_type = "promoted" if applicant.get("was_waitlisted") else "normal"
    else:
        track_type = "normal"

    # 5. Get applicant stage history from current_stage field
    #    current_stage is a Data field — contains the active stage name
    current_stage_name = applicant.current_stage or ""

    # Build stage name → reached_on map from Version log if available
    stage_dates = {}
    try:
        versions = frappe.get_all(
            "Version",
            filters={"ref_doctype": "Applicant", "docname": applicant_name},
            fields=["data", "creation"],
            order_by="creation asc"
        )
        for v in versions:
            import json
            data = json.loads(v.data or "{}")
            for change in data.get("changed", []):
                if change[0] == "current_stage" and change[2]:
                    stage_dates[change[2]] = str(v.creation)[:10]
    except Exception:
        pass

    # 6. Build stage list with status per stage
    stages_out = []
    current_reached = False

    for idx, stage in enumerate(enabled_stages):
        sname = stage.stage_name

        if sname == current_stage_name:
            stage_status = "active"
            current_reached = True
        elif not current_reached:
            # All stages before current = completed
            stage_status = "completed"
        else:
            # Stages after current = pending
            stage_status = "pending"

        # Override for terminal statuses
        if status == "Rejected" and sname == current_stage_name:
            stage_status = "rejected"
        if status == "Waitlisted" and sname == current_stage_name:
            stage_status = "waitlisted"

        # Show action button only if applicant is active at this stage
        show_action = (
            stage_status == "active"
            and stage.requires_applicant_action
        )

        stages_out.append({
            "sequence":              stage.sequence_no,
            "stage_name":            sname,
            "stage_type":            stage.stage_type or "",
            "status":                stage_status,
            "reached_on":            stage_dates.get(sname, ""),
            "requires_action":       bool(stage.requires_applicant_action),
            "action_label":          stage.action_label or "",
            "action_url":            stage.action_url or "",
            "show_action":           show_action,
        })

    return {
        "track_type":     track_type,
        "stages":         stages_out,
        "current_stage":  current_stage_name,
        "app_status":     status,
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
