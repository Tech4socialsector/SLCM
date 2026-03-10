import frappe

@frappe.whitelist(methods=["POST", "GET"])
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

@frappe.whitelist(methods=["POST", "GET"])
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

@frappe.whitelist(methods=["POST", "GET"])
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

@frappe.whitelist(methods=["POST", "GET"])
def get_user_type():
    """Returns user_type for the currently logged-in user"""
    try:
        user_type = frappe.db.get_value("User", frappe.session.user, "user_type")
        return {"user_type": user_type or "Website User"}
    except Exception as e:
        frappe.log_error(f"get_user_type failed: {e}", "Portal")
        return {"user_type": "Website User"}

def _get_stage_seq(stages, stage_name):
    """Returns sequence number of a stage by name."""
    for s in stages:
        if s.stage_name == stage_name:
            return getattr(s, "sequence", None) or getattr(s, "sequence_no", None) or 0
    return 0

@frappe.whitelist(methods=["POST", "GET"])
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

    # Get intake_type from Program (not Admission Cycle)
    intake_type = frappe.db.get_value(
        "Program", applicant.program, "intake_type"
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

    result_stages = []

    for s in stages:
        seq  = getattr(s, "sequence", None) or getattr(s, "sequence_no", None) or 0
        sd   = str(getattr(s, "start_date", None) or "")
        ed   = str(getattr(s, "end_date", None) or "")
        name = s.stage_name

        # PRIMARY: use applicant.current_stage to find active
        if current_stage_name:
            if name == current_stage_name:
                status = "active"
            elif seq < _get_stage_seq(stages, current_stage_name):
                status = "completed"
            else:
                status = "upcoming"
        # SECONDARY: use date window when current_stage not set
        elif sd and ed:
            if today > ed:
                status = "completed"
            elif sd <= today <= ed:
                status = "active"
            else:
                status = "upcoming"
        else:
            status = "upcoming"

        # Action button: only show on active stage
        stage_type = getattr(s, "stage_type", "") or ""
        action_url   = getattr(s, "action_url", "") or ""
        action_label = getattr(s, "action_label", "") or ""

        if status == "active" and not action_url:
            if stage_type == "Interview":
                action_url   = "/eligibility/interview_management"
                action_label = "Book Interview Slot"
            elif stage_type == "Exam":
                action_url   = "/eligibility/entrance_test_seat_allocation"
                action_label = "Choose Preference"
            elif stage_type in ("Offer Letter", "Fee"):
                action_url   = "/offer_letter/offer-letter-list"
                action_label = "View Offer"

        show_action = status == "active" and bool(action_url)

        result_stages.append({
            "stage_name":    name,
            "stage_type":    stage_type,
            "sequence":      seq,
            "status":        status,
            "show_action":   show_action,
            "action_url":    action_url if show_action else "",
            "action_label":  action_label if show_action else "",
            "start_date":    sd or None,
            "end_date":      ed or None,
        })

    return {
        "stages":     result_stages,
        "app_status": applicant.application_status or "",
        "track_type": "normal",
    }




@frappe.whitelist(methods=["POST", "GET"])
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

@frappe.whitelist()
def get_offer_list(limit_start=0, limit_page_length=10):
    """
    Fetches offer letters with pagination. 
    If admin, fetches all. If applicant, fetches only theirs.
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Authentication required", frappe.PermissionError)

    roles = frappe.get_roles(user)
    is_admin = "Administrator" in roles or "System Manager" in roles or "Admission Admin" in roles
    
    filters = {}
    applicant_name = "System View"
    
    if not is_admin:
        # User is an applicant, filter by their record
        applicant = frappe.db.get_value("Applicant", {"email": user}, "name")
        if not applicant:
            if frappe.db.exists("Applicant", user):
                applicant = user
            else:
                frappe.throw(f"Applicant record not found for user {user}")
        
        filters["applicant"] = applicant
        applicant_name = frappe.db.get_value("Applicant", applicant, "candidate_name") or applicant
    
    # Fetch total count for pagination
    total_count = frappe.db.count("Offer Letter", filters=filters)

    # Fetch offers
    fields = [
        "name", "program", "issued_on", "offer_status", 
        "payment_deadline", "payable_amount", "campus", "applicant"
    ]
    
    # Ensure integer types for pagination
    limit_start = int(limit_start)
    limit_page_length = int(limit_page_length)

    offers = frappe.get_all(
        "Offer Letter", 
        filters=filters, 
        fields=fields, 
        order_by="creation desc",
        limit_start=limit_start,
        limit_page_length=limit_page_length,
        ignore_permissions=True
    )

    return {
        "offers": offers,
        "total_count": total_count,
        "applicant_name": applicant_name,
        "is_admin": is_admin,
        "currency": frappe.defaults.get_global_default("currency") or "INR"
    }

@frappe.whitelist(methods=["POST", "GET"])
def download_admit_card(admit_card):
    """
    Custom download function for Admit Card that bypasses standard print permissions
    after verifying that the current user owns the application.
    """
    user = frappe.session.user
    applicant_name = frappe.db.get_value("Applicant", {"email": user}, "name")
    
    try:
        doc = frappe.get_doc("Entrance Test Seat Allocation", admit_card, ignore_permissions=True)
    except frappe.DoesNotExistError:
        frappe.throw("Admit Card not found")

    if not applicant_name or doc.applicant != applicant_name:
        if "Admission Admin" not in frappe.get_roles() and "System Manager" not in frappe.get_roles():
            frappe.throw("Not authorized", frappe.PermissionError)

    is_rescheduled = (doc.is_rescheduled == 1 or doc.entrance_test_status == "Rescheduled")
    status = doc.re_allocation_status if is_rescheduled else doc.allocation_status
    
    if status not in ["Allocated", "Reallocated"]:
        frappe.throw("Admit Card is only available after seat allocation is confirmed.")

    field_to_check = "reschedule_admit_card" if is_rescheduled else "admit_card"
    stored_file_url = getattr(doc, field_to_check)

    if not stored_file_url:
        from slcm.admission.doctype.entrance_test_list.entrance_test_list import generate_and_store_admit_card
        stored_file_url = generate_and_store_admit_card(doc.name, is_rescheduled=is_rescheduled)
        if stored_file_url:
            doc.reload()

    if stored_file_url:
        file_doc = frappe.get_doc("File", {"file_url": stored_file_url})
        frappe.local.response.filename = f"Admit_Card_{doc.applicant}.pdf"
        frappe.local.response.filecontent = file_doc.get_content()
        frappe.local.response.type = "download"
    else:
        frappe.throw("Admit Card generation failed. Please contact the admission office.")

@frappe.whitelist(methods=["POST", "GET"])
def download_application(applicant_name):
    """
    Generates and downloads the Applicant PDF for the owner.
    """
    user = frappe.session.user
    try:
        applicant = frappe.get_doc("Applicant", applicant_name, ignore_permissions=True)
    except frappe.DoesNotExistError:
        frappe.throw("Application not found")

    if applicant.owner != user and applicant.email != user:
        if "Admission Admin" not in frappe.get_roles() and "System Manager" not in frappe.get_roles():
            frappe.throw("Not permitted", frappe.PermissionError)
    
    frappe.flags.ignore_print_permissions = True
    pdf_content = frappe.get_print("Applicant", applicant_name, "Applicant Application Form", as_pdf=True, doc=applicant)
    
    frappe.local.response.filename = f"Application_{applicant_name}.pdf"
    frappe.local.response.filecontent = pdf_content
    frappe.local.response.type = "download"

@frappe.whitelist(methods=["POST", "GET"])
def download_receipt(receipt_name):
    """
    Generates and downloads the Applicant Payment Receipt PDF for the owner.
    """
    user = frappe.session.user
    try:
        receipt = frappe.get_doc("Applicant Payment Receipt", receipt_name, ignore_permissions=True)
    except frappe.DoesNotExistError:
        frappe.throw("Receipt not found")

    # Check if this user owns the receipt (via the Applicant record)
    applicant_email = frappe.db.get_value("Applicant", receipt.applicant, "email")
    
    if receipt.owner != user and applicant_email != user:
        if "Admission Admin" not in frappe.get_roles() and "System Manager" not in frappe.get_roles():
            frappe.throw("Not permitted", frappe.PermissionError)
    
    frappe.flags.ignore_print_permissions = True
    # Try to find a specific print format
    print_format = "Applicant Payment Receipt Format" # Fallback
    
    pdf_content = frappe.get_print("Applicant Payment Receipt", receipt_name, print_format, as_pdf=True, doc=receipt)
    
    frappe.local.response.filename = f"Receipt_{receipt_name}.pdf"
    frappe.local.response.filecontent = pdf_content
    frappe.local.response.type = "download"

@frappe.whitelist(methods=["POST", "GET"])
def download_offer_letter(offer_letter):
    """
    Generates and downloads the Offer Letter PDF for the owner.
    """
    user = frappe.session.user
    try:
        ol = frappe.get_doc("Offer Letter", offer_letter, ignore_permissions=True)
    except frappe.DoesNotExistError:
        frappe.throw("Offer Letter not found")

    applicant_name = ol.applicant
    applicant = frappe.get_doc("Applicant", applicant_name, ignore_permissions=True)
    
    if applicant.owner != user and applicant.email != user:
        if "Admission Admin" not in frappe.get_roles() and "System Manager" not in frappe.get_roles():
            frappe.throw("Not permitted", frappe.PermissionError)
    
    # Check if PDF already stored
    if ol.offer_letter_pdf:
        try:
            file_doc = frappe.get_doc("File", {"file_url": ol.offer_letter_pdf})
            frappe.local.response.filename = f"Offer_Letter_{applicant_name}.pdf"
            frappe.local.response.filecontent = file_doc.get_content()
            frappe.local.response.type = "download"
            return
        except Exception:
            pass

    # Generate PDF
    frappe.flags.ignore_print_permissions = True
    pdf_content = frappe.get_print("Offer Letter", offer_letter, as_pdf=True, doc=ol)
    
    frappe.local.response.filename = f"Offer_Letter_{applicant_name}.pdf"
    frappe.local.response.filecontent = pdf_content
    frappe.local.response.type = "download"

